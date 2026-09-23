# Docstring del módulo: describe que cada nodo recibe el estado y devuelve
# SOLO las llaves que modifica (patrón de LangGraph).
# Lógica: este archivo contiene TODA la lógica del validador. Los nodos
# que usan Python puro (prevalidar, puntuar, finalizar) son gratuitos.
# Los nodos que usan LLM (analizar, invest, ambigüedad, criterios, reescribir)
# llaman a las cadenas de LangChain.
"""Nodos del grafo. Cada nodo recibe el estado y devuelve SOLO las llaves que modifica."""
from __future__ import annotations  # Anotaciones de tipo diferidas (PEP 563)

import functools  # Para el decorador @wraps que preserva metadatos de funciones
import re         # Expresiones regulares para detectar patrones en el texto
import time       # Para medir el tiempo de ejecución de cada nodo
from typing import Any, Callable  # Any: tipo comodín. Callable: tipo para funciones

from langchain_core.runnables import Runnable  # Cadena ejecutable de LangChain

from .config import Settings, get_settings  # Configuración del sistema
from .schemas import (  # Modelos Pydantic que el LLM debe devolver
    AmbiguityReport,
    FinalResult,
    InvestEvaluation,
    Prevalidation,
    RelevanceResult,
    Veredicto,
)
from .state import GraphState, TraceEntry  # Tipos de estado y entrada de traza

# Contexto por defecto si no se proporciona uno específico.
# Sintaxis: constante en MAYÚSCULAS por convención.
# Lógica: se usa como fallback cuando el usuario no pasa --context al CLI.
DEFAULT_CONTEXT = "Aplicación para consultar rutas, horarios y ubicación de las busetas."

# Lista de términos vagos que el prevalidador detecta automáticamente.
# Sintaxis: lista de strings.
# Lógica: si la historia contiene palabras como "rápido", "fácil", "mejor",
# el prevalidador las marca como advertencias porque son subjetivas.
VAGUE_TERMS = [
    "rápido", "rápida", "rápidamente", "fácil", "fácilmente", "sencillo", "simple",
    "eficiente", "amigable", "intuitivo", "mejor", "adecuado", "óptimo", "bonito",
    "moderno", "flexible", "robusto", "cómodo", "etc", "y/o", "algunos", "varios",
    "cualquier", "siempre", "todo", "todos", "mucho", "poco",
]

# Lista de términos técnicos que no deberían aparecer en una historia de usuario.
# Lógica: las historias describen QUÉ quiere el usuario, no CÓMO se implementa.
TECH_TERMS = [
    "base de datos", "sql", "api", "endpoint", "json", "react", "flutter", "firebase",
    "mysql", "postgres", "botón", "boton", "dropdown", "tabla", "microservicio", "servidor",
]

# Regex para extraer el ID de la historia (ej: "HU-01", "HU 02").
# Sintaxis: re.compile() compila la regex para uso repetido (más eficiente).
# Lógica: busca al inicio de línea un patrón como "HU-01:", "HU 02.", etc.
ID_PREFIX = re.compile(r"^\s*[*_`]*\s*(HU[-\s]?\d+)\s*[*_`]*\s*[:.\-–—]\s*", re.IGNORECASE)


# ───────────────────────── utilidades ─────────────────────────

# _fmt_list: formatea una lista de strings como items de viñeta Markdown.
# Sintaxis: "\n".join(...) une los elementos con saltos de línea.
# Lógica: si la lista está vacía, retorna el valor por defecto "Ninguna".
def _fmt_list(items: list[str], empty: str = "Ninguna") -> str:
    return "\n".join(f"- {i}" for i in items) if items else empty


# _story: extrae la historia limpia del estado.
# Sintaxis: state.get("prevalidation") retorna None si no existe.
# Lógica: si hay prevalidación con clean_story, usa esa (sin ID ni espacios
# extra). Si no, usa el raw_story tal cual.
def _story(state: GraphState) -> str:
    pv = state.get("prevalidation")
    return pv.clean_story if pv and pv.clean_story else state["raw_story"]


# _context: extrae el contexto del proyecto del estado.
# Sintaxis: or es un operador de cortocircuito: si la izquierda es falsa, retorna la derecha.
# Lógica: si no hay contexto en el estado, usa el configurado en .env. Si no hay ninguno, usa DEFAULT_CONTEXT.
# NOTA: esta función se define dentro de make_nodes() para tener acceso a settings.
# Se documenta aquí como referencia.


# _fmt_ambiguities: formatea las ambigüedades detectadas para enviarlas al LLM.
# Lógica: si no hay ambigüedades, retorna "Ninguna detectada". Si las hay,
# las formatea como lista de viñetas con el fragmento, problema y pregunta.
def _fmt_ambiguities(amb: AmbiguityReport | None) -> str:
    if not amb or not amb.items:
        return "Ninguna detectada"
    return "\n".join(f'- "{i.fragmento}": {i.problema} (Pregunta: {i.pregunta_aclaratoria})' for i in amb.items)


# _fmt_weak_points: formatea los puntos débiles INVEST para enviarlos al LLM.
# Lógica: solo incluye los criterios que NO cumplen (puntaje < 4).
# Si todos cumplen, retorna "Ninguno relevante".
def _fmt_weak_points(inv: InvestEvaluation | None) -> str:
    if not inv:
        return "Sin evaluación"
    rows = [f"- {k} ({c.puntaje}/5): {c.sugerencia}" for k, c in inv.items().items() if c.puntaje < 4]
    return "\n".join(rows) if rows else "Ninguno relevante"


# compute_verdict: regla determinista que decide el veredicto FINAL.
# Sintaxis: función con parámetros tipados, retorna un Veredicto (Literal).
# Lógica: el LLM NO decide el veredicto. Python aplica reglas fijas:
# 1) Ambigüedad alta → requiere_reescritura.
# 2) Puntaje mínimo <= 2 O promedio < min_threshold → requiere_reescritura.
# 3) Promedio >= approve_threshold, mínimo >= 3 y ambigüedad baja → aprobada.
# 4) Cualquier otro caso → aprobada_con_observaciones.
def compute_verdict(inv: InvestEvaluation, amb: AmbiguityReport, s: Settings) -> Veredicto:
    """Regla determinista: el veredicto NO lo decide el LLM, lo decide Python."""
    if amb.nivel == "alta":
        return "requiere_reescritura"
    if inv.minimo <= 2 or inv.promedio < s.min_threshold:
        return "requiere_reescritura"
    if inv.promedio >= s.approve_threshold and inv.minimo >= 3 and amb.nivel == "baja":
        return "aprobada"
    return "aprobada_con_observaciones"


# traced: decorador que mide tiempo, captura errores y registra la traza.
# Sintaxis: decorador de decoradores (recibe nombre, retorna el decorador real).
# Lógica: cada nodo se envuelve con @traced("nombre"). Esto:
# 1) Mide el tiempo de ejecución en milisegundos.
# 2) Si el nodo falla, captura la excepción (sin romper el grafo).
# 3) Registra una entrada de traza con: nodo, estado, tiempo y detalle.
def traced(name: str) -> Callable:
    """Decorador: mide tiempo, captura errores y registra la traza sin romper el grafo."""

    def deco(fn: Callable[[GraphState], dict[str, Any]]):
        @functools.wraps(fn)  # Preserva el nombre y docstring de la función original
        def wrapper(state: GraphState) -> dict[str, Any]:
            t0 = time.perf_counter()  # Marca el tiempo de inicio
            try:
                update = fn(state)    # Ejecuta el nodo real
                status = "ok"
            except Exception as exc:  # noqa: BLE001 - queremos capturar todo
                update = {"errors": [f"{name}: {type(exc).__name__}: {str(exc)[:300]}"]}
                update["_detail"] = str(exc)[:160]
                status = "error"
            detail = update.pop("_detail", "")  # Extrae el detalle y lo quita del update
            entry = TraceEntry(
                node=name, status=status, ms=int((time.perf_counter() - t0) * 1000), detail=detail
            )
            update["trace"] = [entry]  # Agrega la traza al update
            return update

        return wrapper

    return deco


# ───────────────────────── fábrica de nodos ─────────────────────────

# make_nodes: crea todas las funciones de nodo del grafo.
# Sintaxis: recibe las cadenas LLM y la configuración. Retorna un dict nombre->función.
# Lógica: cada nodo es una función que recibe el estado y retorna un dict
# con las llaves que modifica. El decorador @traced agrega traza y manejo de errores.
def make_nodes(chains: dict[str, Runnable] | None, settings: Settings | None = None) -> dict[str, Callable]:
    s = settings or get_settings()  # Usa settings pasados o los del .env

    # Helper interno: invoca una cadena LLM por nombre.
    # Lógica: si la cadena no existe (ej: no hay proveedores), lanza error.
    def _call(chain_name: str, payload: dict[str, Any]):
        if chains is None or chain_name not in chains:
            raise RuntimeError("Cadena LLM no disponible.")
        return chains[chain_name].invoke(payload)

    # Helper interno: extrae el contexto del proyecto del estado.
    # Lógica: si no hay contexto en el estado, usa el configurado en .env. Si no hay ninguno, usa DEFAULT_CONTEXT.
    def _context(state: GraphState) -> str:
        return (state.get("project_context") or s.project_context or DEFAULT_CONTEXT).strip()

    # ──── 1) Prevalidación: Python puro, cero costo de LLM ────
    # Lógica: analiza el texto sin usar el LLM. Detecta ID, rol, acción,
    # beneficio, errores bloqueantes, advertencias y términos vagos.
    @traced("prevalidar")
    def prevalidate(state: GraphState) -> dict[str, Any]:
        # Limpia el texto: une espacios múltiples y quita comillas decorativas
        raw = state.get("raw_story", "") or ""
        text = " ".join(raw.split()).strip().strip('""')

        # Extrae el ID de la historia (ej: "HU-01") usando regex
        story_id = None
        m = ID_PREFIX.match(text)
        if m:
            story_id = m.group(1).upper().replace(" ", "-")  # Normaliza: "HU 01" → "HU-01"
            text = text[m.end():].strip()  # Quita el ID del texto

        # Detecta patrones clave en el texto (rol, acción, beneficio)
        low = text.lower()
        has_role = bool(re.search(r"\bcomo\b", low))          # ¿Tiene "como ..."?
        has_action = bool(re.search(r"\b(quiero|necesito|deseo|puedo|debo poder)\b", low))  # ¿Tiene "quiero ..."?
        has_benefit = bool(re.search(r"\bpara\s+(que\s+)?\w+", low))  # ¿Tiene "para ..."?

        # Validaciones de longitud
        errors: list[str] = []
        warnings: list[str] = []
        if len(text) < 20:
            errors.append("El texto es demasiado corto para ser una historia de usuario (mínimo 20 caracteres).")
        if len(text) > 800:
            errors.append("El texto supera 800 caracteres: parece una épica o varios requisitos. Divídelo.")
        if not errors and not has_role and not has_action:
            errors.append("No se detecta rol ('Como ...') ni acción ('quiero ...'): no parece una historia de usuario.")

        # Advertencias (no bloquean, pero se muestran al usuario)
        if not errors:
            if not has_role:
                warnings.append("No se identifica el rol (falta 'Como ...').")
            if not has_action:
                warnings.append("No se identifica la acción (falta 'quiero ...').")
            if not has_benefit:
                warnings.append("No se identifica el beneficio (falta 'para ...').")
            if len(re.findall(r"\bquiero\b", low)) > 1:
                warnings.append("Contiene más de un 'quiero': posible historia doble.")
            if len(re.findall(r"\by\b", low)) >= 3:
                warnings.append("Muchas conjunciones 'y': posible historia demasiado grande.")
            # Detecta términos técnicos (la historia debería describir QUÉ, no CÓMO)
            tech = [t for t in TECH_TERMS if re.search(rf"\b{re.escape(t)}\b", low)]
            if tech:
                warnings.append(f"Posibles detalles de implementación: {', '.join(tech)}.")

        # Detecta términos vagos en el texto
        vague = [t for t in VAGUE_TERMS if re.search(rf"(?<!\w){re.escape(t)}(?!\w)", low)]

        # Construye el objeto Prevalidation con todos los resultados
        pv = Prevalidation(
            ok=not errors,              # OK si no hay errores bloqueantes
            story_id=story_id,          # ID extraído (ej: "HU-01")
            clean_story=text,           # Texto limpio sin ID
            word_count=len(text.split()),  # Número de palabras
            has_role=has_role,          # ¿Tiene "como ..."?
            has_action=has_action,      # ¿Tiene "quiero ..."?
            has_benefit=has_benefit,    # ¿Tiene "para ..."?
            blocking_errors=errors,     # Errores que bloquean el flujo
            warnings=warnings,          # Advertencias no bloqueantes
            vague_terms=vague,          # Términos vagos detectados
        )
        return {"prevalidation": pv, "_detail": "OK" if pv.ok else errors[0]}

    # ──── 1b) Relevancia: verifica si la historia es para este proyecto ────
    # Lógica: después de prevalidar (formato OK), verifica si la historia tiene
    # relación con el dominio del proyecto. Si no es relevante, se rechaza
    # sin gastar tokens en análisis INVEST, ambigüedad, etc.
    @traced("relevancia")
    def relevance(state: GraphState) -> dict[str, Any]:
        tagged = _call(
            "relevance",
            {"story": _story(state), "context": _context(state)},
        )
        r = tagged.data  # Objeto RelevanceResult
        return {"relevance": r, "providers": [tagged.provider],
                "_detail": f"{tagged.provider} · relevancia={r.puntaje_relevancia}/10"}

    # ──── 2) Análisis LLM ────
    # Lógica: envía la historia al LLM para que descomponga en rol/acción/beneficio
    # y confirme si es realmente una historia de usuario.
    @traced("analizar")
    def analyze(state: GraphState) -> dict[str, Any]:
        pv = state["prevalidation"]
        # Invoca la cadena "analysis" con la historia, contexto y advertencias
        tagged = _call(
            "analysis",
            {"story": _story(state), "context": _context(state), "warnings": _fmt_list(pv.warnings)},
        )
        a = tagged.data  # Objeto StoryAnalysis con es_historia_usuario, rol, accion, beneficio
        return {"analysis": a, "providers": [tagged.provider], "_detail": f"{tagged.provider} · historia={a.es_historia_usuario}"}

    # ──── 3a) INVEST (paralelo con ambigüedad) ────
    # Lógica: evalúa la historia contra los 6 criterios INVEST (1-5 cada uno).
    # Se ejecuta en paralelo con el nodo de ambigüedad.
    @traced("invest")
    def invest(state: GraphState) -> dict[str, Any]:
        a = state["analysis"]  # Necesita el análisis previo para rol/acción/beneficio
        tagged = _call(
            "invest",
            {
                "story": _story(state),
                "context": _context(state),
                "rol": a.rol or "(no aparece)",
                "accion": a.accion or "(no aparece)",
                "beneficio": a.beneficio or "(no aparece)",
            },
        )
        return {"invest": tagged.data, "providers": [tagged.provider], "_detail": f"{tagged.provider} · promedio={tagged.data.promedio}"}

    # ──── 3b) Ambigüedad (paralelo con INVEST) ────
    # Lógica: detecta ambigüedades en la historia (adjetivos vagos, cantidades
    # sin definir, etc.) y las clasifica por nivel (baja/media/alta).
    @traced("ambiguedad")
    def ambiguity(state: GraphState) -> dict[str, Any]:
        pv = state["prevalidation"]
        tagged = _call(
            "ambiguity",
            {
                "story": _story(state),
                "context": _context(state),
                "vague_terms": _fmt_list(pv.vague_terms),  # Términos vagos del prevalidador
            },
        )
        return {"ambiguity": tagged.data, "providers": [tagged.provider], "_detail": f"{tagged.provider} · nivel={tagged.data.nivel}"}

    # ──── 4) Puntaje y veredicto preliminar: Python puro ────
    # Lógica: calcula el promedio INVEST y aplica las reglas deterministas
    # para decidir el veredicto (el LLM NO decide esto).
    # Si invest o ambigüedad fallaron, no hay datos → no calcula veredicto.
    @traced("puntuar")
    def score(state: GraphState) -> dict[str, Any]:
        inv, amb = state.get("invest"), state.get("ambiguity")
        # Si falta invest o ambigüedad (nodo falló), no se puede puntuar
        if not inv or not amb:
            return {"_detail": "skip: faltan datos de invest/ambigüedad"}
        verdict = compute_verdict(inv, amb, s)  # Reglas fijas en Python
        return {
            "invest_score": inv.promedio,           # Promedio de los 6 criterios
            "preliminary_verdict": verdict,          # Veredicto determinista
            "_detail": f"{verdict} · INVEST={inv.promedio}",
        }

    # ──── 5) Criterios de aceptación ────
    # Lógica: genera criterios Gherkin (Dado/Cuando/Entonces) para la historia.
    # Si ya hay reescritura, genera criterios sobre la historia MEJORADA.
    @traced("criterios")
    def criteria(state: GraphState) -> dict[str, Any]:
        rewrite = state.get("rewrite")
        # Si ya se reescribió, usa la historia mejorada; si no, la original
        target = rewrite.historia_mejorada if rewrite else _story(state)
        tagged = _call(
            "criteria",
            {
                "story": target,
                "context": _context(state),
                # Si ya hay reescritura, no envía ambigüedades (ya se resolvieron)
                "ambiguities": _fmt_ambiguities(None if rewrite else state.get("ambiguity")),
            },
        )
        origen = "historia mejorada" if rewrite else "historia original"
        return {
            "criteria": tagged.data,
            "providers": [tagged.provider],
            "_detail": f"{tagged.provider} · {len(tagged.data.criterios)} escenarios ({origen})",
        }

    # ──── 6) Reescritura sugerida ────
    # Lógica: reescribe la historia para que cumpla INVEST. Conserva la intención
    # original, elimina implementación y términos vagos.
    @traced("reescribir")
    def rewrite(state: GraphState) -> dict[str, Any]:
        tagged = _call(
            "rewrite",
            {
                "story": _story(state),
                "context": _context(state),
                "weak_points": _fmt_weak_points(state.get("invest")),  # Criterios débiles
                "ambiguities": _fmt_ambiguities(state.get("ambiguity")),  # Ambigüedades
            },
        )
        return {"rewrite": tagged.data, "providers": [tagged.provider], "_detail": tagged.provider}

    # ──── 7) Resultado estructurado: Python puro ────
    # Lógica: ensambla el FinalResult con toda la información recopilada.
    # Maneja los casos especiales: rechazada, no_evaluada, etc.
    @traced("finalizar")
    def finalize(state: GraphState) -> dict[str, Any]:
        pv = state.get("prevalidation")
        relevance = state.get("relevance")
        analysis = state.get("analysis")
        inv, amb = state.get("invest"), state.get("ambiguity")
        errors = state.get("errors", [])
        story = pv.clean_story if pv and pv.clean_story else state.get("raw_story", "")

        # Caso 1: la prevalidación falló (errores bloqueantes)
        if pv and not pv.ok:
            verdict: Veredicto = "rechazada"
            resumen = "Rechazada en la prevalidación: " + pv.blocking_errors[0]
        # Caso 2: la historia no es relevante para el proyecto
        elif relevance and not relevance.es_relevante:
            verdict = "no_relevante"
            resumen = f"La historia no es relevante para el proyecto (relevancia: {relevance.puntaje_relevancia}/10). {relevance.explicacion}"
        # Caso 3: el LLM determinó que no es historia de usuario
        elif analysis and not analysis.es_historia_usuario:
            verdict = "rechazada"
            resumen = "El análisis indica que el texto no describe una necesidad de usuario: " + analysis.resumen
        # Caso 4: fallaron los nodos LLM (invest o ambigüedad)
        elif not (inv and amb):
            verdict = "no_evaluada"
            resumen = "No se pudo completar la evaluación por errores técnicos (revisa la traza)."
        # Caso 5: todo normal, usa el veredicto preliminar
        else:
            verdict = state.get("preliminary_verdict") or compute_verdict(inv, amb, s)  # type: ignore[assignment]
            resumen = {
                "aprobada": "La historia cumple INVEST y no tiene ambigüedades relevantes.",
                "aprobada_con_observaciones": "La historia es aceptable, pero tiene puntos por mejorar.",
                "requiere_reescritura": "La historia necesita reescribirse antes de entrar al backlog.",
            }[verdict] + f" Promedio INVEST: {inv.promedio}/5."

        # Construye el objeto FinalResult con toda la información
        result = FinalResult(
            historia_original=story,
            story_id=pv.story_id if pv else None,
            veredicto=verdict,
            puntaje_invest=inv.promedio if inv else None,
            resumen=resumen,
            prevalidacion=pv,
            relevancia=relevance,
            analisis=analysis,
            invest=inv,
            ambiguedad=amb,
            criterios=state.get("criteria"),
            reescritura=state.get("rewrite"),
            proveedores_usados=sorted(set(state.get("providers", []))),  # Proveedores únicos, ordenados
            errores=errors,
        )
        return {"result": result, "_detail": verdict}

    # Retorna el diccionario de nodos: nombre -> función
    return {
        "prevalidar": prevalidate,
        "relevancia": relevance,
        "analizar": analyze,
        "invest": invest,
        "ambiguedad": ambiguity,
        "puntuar": score,
        "criterios": criteria,
        "reescribir": rewrite,
        "finalizar": finalize,
    }

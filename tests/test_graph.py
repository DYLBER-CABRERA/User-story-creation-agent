# test_graph.py: Pruebas del grafo de validación SIN usar LLM real.
# Lógica: se inyectan cadenas falsas (fake_chains) que devuelven datos predefinidos.
# Esto permite probar el flujo del grafo, las reglas de negocio y el manejo de errores
# sin depender de proveedores externos (Gemini, Ollama, etc.).
# IMPORTANTE: estas pruebas verifican la LÓGICA, no la calidad de las respuestas del LLM.

"""Pruebas sin LLM real: se inyectan cadenas falsas para verificar el flujo y las reglas."""
import pytest  # Framework de pruebas
from langchain_core.prompts import ChatPromptTemplate  # Plantilla de prompts (para test de fallback)
from langchain_core.runnables import RunnableLambda  # Runnable que envuelve una función lambda

from validador.chains import Tagged, build_chain  # build_chain: crea cadenas con fallback
from validador.graph import build_graph  # build_graph: construye el grafo LangGraph
from validador.schemas import (  # Modelos Pydantic que se usan en las pruebas
    AcceptanceCriteria, AcceptanceCriterion, AmbiguityItem, AmbiguityReport,
    InvestCriterion, InvestEvaluation, RewriteSuggestion, StoryAnalysis,
)

# GOOD: historia de usuario válida que cumple todos los criterios INVEST.
# Se usa como base en la mayoría de las pruebas.
GOOD = "HU-01: Como pasajero, quiero ver la lista de todas las rutas de buseta, para saber qué rutas existen en Manizales."


# ───────────── Helpers (funciones de utilidad) ─────────────

# crit(p): crea un InvestCriterion con el puntaje dado.
# Lógica: si el puntaje es 5, la sugerencia está vacía (cumple perfecto).
# Si es menor a 5, tiene una sugerencia genérica ("mejorar").
def crit(p): return InvestCriterion(puntaje=p, justificacion="ok", sugerencia="" if p == 5 else "mejorar")

# invest(p): crea un InvestEvaluation donde TODOS los criterios tienen el mismo puntaje.
# Lógica: simplifica las pruebas al no tener que crear cada criterio individualmente.
def invest(p): return InvestEvaluation(**{k: crit(p) for k in ["independent", "negotiable", "valuable", "estimable", "small", "testable"]})

# gc(): crea un AcceptanceCriteria con 3 criterios genéricos.
# Lógica: los criterios tienen valores mínimos ("d", "c", "e") solo para satisfacer el esquema.
def gc(): return AcceptanceCriteria(criterios=[AcceptanceCriterion(escenario=f"e{i}", dado="d", cuando="c", entonces="e") for i in range(3)])

# rw(): crea un RewriteSuggestion con una historia mejorada genérica.
# Lógica: la historia reescrita debe tener el formato "Como ..., quiero ..., para ..."
# para pasar la validación de RewriteSuggestion._formato.
def rw(): return RewriteSuggestion(historia_mejorada="Como pasajero, quiero ver rutas, para viajar.", cambios=["x"])


# fake_chains: crea un diccionario de cadenas falsas para inyectar en el grafo.
# Parámetros:
#   inv_score: puntaje INVEST para todos los criterios (default: 5 = perfecto)
#   amb: tupla (nivel, cantidad) de ambigüedades (default: ("baja", 0))
#   is_story: si True, el LLM dice que es historia de usuario (default: True)
#   fail: nombre de la cadena que debe fallar (default: None = ninguna falla)
# Lógica: cada cadena retorna un Tagged con provider="fake". Si fail==nombre,
# lanza RuntimeError simulando una caída del LLM.
def fake_chains(inv_score=5, amb=("baja", 0), is_story=True, fail=None):
    def wrap(name, factory):
        def run(_):
            if fail == name:
                raise RuntimeError("caída simulada")  # Simula error del LLM
            return Tagged(factory(), "fake")  # Tagged: envuelve el dato con el nombre del proveedor
        return RunnableLambda(run)  # RunnableLambda: convierte una función en un runnable de LangChain

    # Crea las ambigüedades según la cantidad especificada
    items = [AmbiguityItem(fragmento="rápido", problema="p", pregunta_aclaratoria="q") for _ in range(amb[1])]
    return {
        "analysis": wrap("analysis", lambda: StoryAnalysis(es_historia_usuario=is_story, rol="pasajero", accion="ver", beneficio="saber", resumen="r")),
        "invest": wrap("invest", lambda: invest(inv_score)),
        "ambiguity": wrap("ambiguity", lambda: AmbiguityReport(items=items, nivel=amb[0])),
        "criteria": wrap("criteria", gc),
        "rewrite": wrap("rewrite", rw),
    }


# run: ejecuta el grafo completo con cadenas falsas.
# Lógica: construye el grafo, invoca con la historia y retorna el estado completo.
def run(story, **kw):
    g = build_graph(chains=fake_chains(**kw))
    return g.invoke({"raw_story": story})


# nodes: extrae la lista de nombres de nodos ejecutados de la traza.
# Lógica: la traza es una lista de dicts con la llave "node".
def nodes(out): return [t["node"] for t in out["trace"]]


# ───────────── Pruebas del flujo principal ─────────────

# test_aprobada_flujo_lineal: verifica que una historia válida sea aprobada.
# Lógica: GOOD cumple todos los criterios, así que el veredicto debe ser "aprobada",
# el ID debe ser "HU-01", no debe pasar por "reescribir" y sí debe tener criterios.
def test_aprobada_flujo_lineal():
    out = run(GOOD)
    r = out["result"]
    assert r.veredicto == "aprobada" and r.story_id == "HU-01"
    assert "reescribir" not in nodes(out) and r.criterios is not None


# test_prevalidacion_corta_el_flujo_sin_llm: verifica que una historia muy corta sea rechazada
# ANTES de llegar a cualquier nodo LLM.
# Lógica: "hola" tiene solo 5 caracteres, el prevalidador lo detecta como error bloqueante.
# El flujo debe ser: prevalidar → finalizar (sin pasar por analizar, invest, etc.)
def test_prevalidacion_corta_el_flujo_sin_llm():
    out = run("hola")
    assert out["result"].veredicto == "rechazada"
    assert nodes(out) == ["prevalidar", "finalizar"]


# test_no_es_historia: verifica que si el LLM dice que no es historia, sea rechazada.
# Lógica: is_story=False hace que el nodo "analizar" devuelva es_historia_usuario=False.
# El flujo debe ser: prevalidar → analizar → finalizar (sin pasar por invest, etc.)
def test_no_es_historia():
    out = run(GOOD, is_story=False)
    assert out["result"].veredicto == "rechazada" and "invest" not in nodes(out)


# test_requiere_reescritura_genera_criterios_sobre_mejorada: verifica que cuando
# la historia requiere reescritura, los criterios se generan sobre la HISTORIA MEJORADA.
# Lógica: inv_score=2 hace que el veredicto sea "requiere_reescritura".
# El flujo debe ser: ... → reescribir → criterios (criterios DESPUÉS de reescribir).
def test_requiere_reescritura_genera_criterios_sobre_mejorada():
    out = run(GOOD, inv_score=2)
    r = out["result"]
    assert r.veredicto == "requiere_reescritura"
    n = nodes(out)
    assert n.index("reescribir") < n.index("criterios") and r.reescritura and r.criterios


# test_ambiguedad_alta_fuerza_reescritura: verifica que ambigüedad alta
# fuerza el veredicto "requiere_reescritura" aunque el puntaje INVEST sea perfecto.
# Lógica: compute_verdict() prioriza la ambigüedad alta sobre el puntaje.
def test_ambiguedad_alta_fuerza_reescritura():
    out = run(GOOD, inv_score=5, amb=("alta", 2))
    assert out["result"].veredicto == "requiere_reescritura"


# test_observaciones_pasa_por_criterios_y_luego_reescritura: verifica el flujo
# cuando el veredicto es "aprobada_con_observaciones".
# Lógica: inv_score=4, amb=("media", 1) → veredicto = "aprobada_con_observaciones".
# El flujo debe ser: ... → criterios → reescribir (criterios ANTES de reescribir).
def test_observaciones_pasa_por_criterios_y_luego_reescritura():
    out = run(GOOD, inv_score=4, amb=("media", 1))
    n = nodes(out)
    assert out["result"].veredicto == "aprobada_con_observaciones"
    assert n.index("criterios") < n.index("reescribir")
    assert n.count("criterios") == 1 and n.count("reescribir") == 1


# ───────────── Pruebas de paralelismo ─────────────

# test_paralelismo_invest_y_ambiguedad_acumulan_trazas: verifica que los nodos
# "invest" y "ambiguedad" corren en paralelo y ambos escriben en la traza.
# Lógica: en el grafo, invest y ambiguedad están conectados desde "analizar"
# y se ejecutan en paralelo. Ambos deben aparecer en la traza ANTES de "puntuar".
def test_paralelismo_invest_y_ambiguedad_acumulan_trazas():
    n = nodes(run(GOOD))
    assert "invest" in n and "ambiguedad" in n and n.index("puntuar") > max(n.index("invest"), n.index("ambiguedad"))


# ───────────── Pruebas de manejo de errores ─────────────

# test_fallo_de_llm_da_no_evaluada: verifica que si el nodo "analysis" falla,
# el veredicto sea "no_evaluada" y se registren errores.
# Lógica: fail="analysis" hace que la cadena "analysis" lance RuntimeError.
# El grafo debe capturar el error y continuar hasta "finalizar" con veredicto "no_evaluada".
def test_fallo_de_llm_da_no_evaluada():
    out = run(GOOD, fail="analysis")
    assert out["result"].veredicto == "no_evaluada" and out["result"].errores


# test_fallo_de_criterios_no_tumba_el_resultado: verifica que si el nodo "criteria" falla,
# el resultado final AÚN se genera (con veredicto correcto) pero con errores.
# Lógica: fail="criteria" hace que la cadena "criteria" lance RuntimeError.
# El nodo "finalizar" debe generar el resultado de todas formas.
def test_fallo_de_criterios_no_tumba_el_resultado():
    out = run(GOOD, inv_score=4, amb=("media", 1), fail="criteria")
    assert out["result"].veredicto == "aprobada_con_observaciones" and out["result"].errores
    assert nodes(out).count("criterios") == 1


# ───────────── Pruebas de validación Pydantic ─────────────

# test_pydantic_rechaza_salidas_incoherentes: verifica que Pydantic rechace
# datos inválidos que el LLM podría devolver.
# Lógica: InvestCriterion con puntaje=3 y sugerencia vacía → error (debe tener sugerencia).
# AmbiguityReport con nivel="alta" y 0 ítems → error (debe tener >= 2 ítems).
# RewriteSuggestion con historia_mejorada="Ver rutas" → error (debe tener formato "Como ...").
def test_pydantic_rechaza_salidas_incoherentes():
    with pytest.raises(ValueError):
        InvestCriterion(puntaje=3, justificacion="x", sugerencia="")
    with pytest.raises(ValueError):
        AmbiguityReport(items=[], nivel="alta")
    with pytest.raises(ValueError):
        RewriteSuggestion(historia_mejorada="Ver rutas", cambios=["x"])


# ───────────── Prueba de fallback de proveedores ─────────────

# FakeLLM: clase que simula un modelo de lenguaje.
# Lógica: con ok=True responde correctamente. Con ok=False lanza ConnectionError.
# Se usa para probar el mecanismo de fallback de build_chain().
class FakeLLM:
    """Simula un chat model: with_structured_output devuelve un runnable que responde o falla."""
    def __init__(self, ok): self.ok = ok
    def with_structured_output(self, schema):
        def f(_):
            if not self.ok:
                raise ConnectionError("sin red")  # Simula error de conexión
            return StoryAnalysis(es_historia_usuario=True, resumen="r")  # Respuesta válida
        return RunnableLambda(f)


# test_fallback_gemini_a_ollama: verifica que si Gemini falla, se intente con Ollama.
# Lógica: build_chain() recibe una lista de proveedores en orden de prioridad.
# Si el primero falla, intenta con el siguiente. Si todos fallan, lanza error.
# En este test: gemini falla (ok=False), ollama responde (ok=True) → provider="ollama".
# Si gemini responde primero → provider="gemini".
def test_fallback_gemini_a_ollama():
    prompt = ChatPromptTemplate.from_messages([("human", "{story}")])
    chain = build_chain(prompt, StoryAnalysis, [("gemini", FakeLLM(False)), ("ollama", FakeLLM(True))])
    assert chain.invoke({"story": "x"}).provider == "ollama"
    chain2 = build_chain(prompt, StoryAnalysis, [("gemini", FakeLLM(True)), ("ollama", FakeLLM(True))])
    assert chain2.invoke({"story": "x"}).provider == "gemini"

"""Generación de SPECs (especificaciones) por funcionalidad.

Ensambla el documento de las 17 secciones de la guía del Specification Agent
(docs/Guia - Specification Agent.md, sección 7) a partir de:

- docs/alcance-contexto-proyecto.md -> contexto, alcance, reglas, restricciones,
  fuera de alcance, preguntas abiertas y RNF medibles (§14) (fuente única de verdad).
- las historias ya generadas        -> RF (§5), flujos (§8-9), criterios (§11)
  y trazabilidad (§16).

Regla de la guía (§11): NO se inventa contenido. Lo que no esté definido se marca
explícitamente como "Pendiente" con su responsable.

Asignación historia -> SPEC: por posición dentro de cada rol (el prompt exige el
orden de temas de temas.py); con módulo len(temas_base) cubre las variantes.

Uso:
    from generador.specs import construir_specs, escribir_specs
    docs = construir_specs(historias)          # historias=None -> esqueletos pendientes
    escribir_specs(docs)                       # escribe docs/specs/SPEC-XXX-slug.md

CLI:
    python -m generador.specs                          # esqueleto desde el alcance
    python -m generador.specs --historias hist.json    # SPECs completas
    python -m generador.specs --responder              # control humano: responder preguntas (§12)
    python -m generador.specs --aprobar 001 --por "Prof. X"   # aprueba (falla si hay pendientes)
    python -m generador.specs --congelar 001           # pasa a FROZEN

Control humano (guía §12): respuestas y estados (borrador → APROBADA → FROZEN)
se persisten en docs/specs/control.json y se comparten con la app Streamlit.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .schemas import HistoriasGeneradas
from .temas import TEMAS_POR_ROL

RAIZ = Path(__file__).resolve().parent.parent
ALCANCE_PATH = RAIZ / "docs" / "alcance-contexto-proyecto.md"
SPECS_DIR = RAIZ / "docs" / "specs"
CONTROL_PATH = SPECS_DIR / "control.json"


@dataclass(frozen=True)
class Funcionalidad:
    num: int
    slug: str
    nombre: str
    actores: tuple[str, ...]
    objetivo: str
    clave_alcance: str   # nombre del bullet en §5 del documento de alcance
    brs: tuple[str, ...]  # reglas de negocio aplicables (§7 del alcance)


CATALOGO: tuple[Funcionalidad, ...] = (
    Funcionalidad(1, "consulta-de-rutas", "Consulta de rutas", ("Pasajero",),
                  "Permitir al pasajero consultar el catálogo de rutas de buseta de Manizales con su recorrido en el mapa.",
                  "Consulta de rutas", ("BR-01",)),
    Funcionalidad(2, "consulta-de-horarios", "Consulta de horarios", ("Pasajero",),
                  "Informar los horarios, frecuencia y días de operación de cada ruta.",
                  "Consulta de horarios", ("BR-01",)),
    Funcionalidad(3, "seguimiento-gps-eta", "Seguimiento en tiempo real (GPS/ETA)", ("Pasajero",),
                  "Mostrar la ubicación en tiempo real de las busetas y el tiempo estimado de llegada (ETA) a una parada.",
                  "Seguimiento en tiempo real", ("BR-01",)),
    Funcionalidad(4, "planificacion-de-viaje", "Planificación de viaje", ("Pasajero",),
                  "Ayudar al pasajero a planificar un viaje indicando origen y destino.",
                  "Planificación de viaje", ("BR-01",)),
    Funcionalidad(5, "busqueda-y-filtros", "Búsqueda y filtros", ("Pasajero",),
                  "Permitir buscar rutas por número, nombre, barrio o punto de interés.",
                  "Búsqueda y filtros", ("BR-01",)),
    Funcionalidad(6, "modulo-administrativo", "Módulo administrativo", ("Administrador",),
                  "Permitir al administrador crear y actualizar rutas, horarios, paradas y busetas.",
                  "Módulo administrativo", ("BR-03",)),
    Funcionalidad(7, "modulo-de-conductores", "Módulo de conductores", ("Conductor",),
                  "Permitir al conductor consultar su ruta asignada, iniciar/finalizar el recorrido y reportar la posición de la buseta.",
                  "Módulo de conductores", ("BR-05",)),
    Funcionalidad(8, "favoritas", "Favoritas", ("Pasajero",),
                  "Permitir al pasajero guardar rutas o paradas frecuentes para encontrarlas rápido.",
                  "Favoritas", ("BR-02",)),
    Funcionalidad(9, "notificaciones", "Notificaciones", ("Pasajero",),
                  "Avisar al pasajero cuando la buseta esté por llegar a una parada que le interesa.",
                  "Notificaciones", ("BR-02",)),
    Funcionalidad(10, "uso-sin-cuenta", "Uso sin cuenta", ("Pasajero",),
                  "Permitir consultar la app sin obligar a crear una cuenta.",
                  "Uso sin cuenta", ("BR-01", "BR-02")),
    Funcionalidad(11, "avisos-generales", "Avisos generales", ("Administrador",),
                  "Permitir al administrador publicar avisos generales (cambios, suspensiones, festivos).",
                  "Avisos generales", ("BR-04",)),
    Funcionalidad(12, "estadisticas-basicas", "Estadísticas básicas", ("Administrador",),
                  "Mostrar al administrador estadísticas básicas de uso de la app.",
                  "Estadísticas básicas", ("BR-03",)),
)

# Índice de tema base -> número de SPEC, por rol (alineado con temas.py).
# El índice de la historia se toma con módulo para cubrir las variantes.
MAPEO_POR_ROL: dict[str, tuple[int, ...]] = {
    "pasajero": (1, 1, 2, 3, 3, 4, 5, 8, 9, 10),
    "conductor": (7, 7, 7, 7, 7),
    "administrador": (6, 6, 6, 11, 12),
}

# Operación principal de cada SPEC, para redactar sus RNF (guía §2.2/§8).
RNF_OPERACION: dict[int, str] = {
    1: "la consulta de rutas",
    2: "la consulta de horarios",
    3: "la actualización de posición y ETA",
    4: "la planificación de viaje",
    5: "la búsqueda y los filtros",
    6: "las operaciones del módulo administrativo",
    7: "el reporte de posición del conductor",
    8: "la gestión de favoritas",
    9: "el envío de notificaciones",
    10: "la consulta sin cuenta",
    11: "la publicación de avisos",
    12: "la consulta de estadísticas",
}

# RNF medibles generados por SPEC: cada modelo produce una fila en la §6 y una
# pregunta numérica SUG-{nnn}-RNF-{suf}; la cifra la pone el equipo en la
# interfaz/CLI (guía §8: el agente NO inventa valores). `RNF_OPERACION` lleva
# artículo; `_de()` lo flexiona para usarlo tras una preposición (evita "de el").
RNF_MODELOS: tuple[dict, ...] = (
    {
        "suf": "01", "categoria": "Rendimiento", "unidad": "s", "unidad_txt": "segundos",
        "ui": "Tiempo máximo de respuesta",
        "req": "La respuesta {opde} tarda como máximo {valor} segundos bajo carga definida",
    },
    {
        "suf": "02", "categoria": "Disponibilidad", "unidad": "%", "unidad_txt": "% de disponibilidad",
        "ui": "Disponibilidad mínima (ventana mensual)",
        "req": "El servicio que soporta {op} debe estar disponible al menos el {valor}% del tiempo (ventana mensual)",
    },
    {
        "suf": "03", "categoria": "Actualización", "unidad": "s", "unidad_txt": "segundos",
        "ui": "Cadencia máxima de actualización",
        "req": "La información mostrada por {op} se actualiza como máximo cada {valor} segundos",
    },
)


def _de(operacion: str) -> str:
    """'la consulta de rutas' -> 'de la consulta de rutas'; 'el reporte' -> 'del reporte'."""
    for articulo in ("el", "la", "los", "las"):
        if operacion.startswith(articulo + " "):
            resto = operacion[len(articulo) + 1:]
            return ("del " if articulo == "el" else f"de {articulo} ") + resto
    return f"de {operacion}"


def spec_de_historia(rol: str, indice: int) -> int:
    """Número de SPEC (1-12) que recibe la historia `indice`-ésima del rol."""
    base = MAPEO_POR_ROL[rol]
    return base[indice % len(base)]


@dataclass(frozen=True)
class SpecDoc:
    num: int
    slug: str
    nombre: str
    markdown: str

    @property
    def titulo(self) -> str:
        return f"SPEC-{self.num:03d} — {self.nombre}"

    @property
    def nombre_archivo(self) -> str:
        return f"SPEC-{self.num:03d}-{self.slug}.md"


# ───────────────────── lectura del documento de alcance ─────────────────────

def _leer_alcance(path: Path = ALCANCE_PATH) -> dict[str, str]:
    """{'1. Descripción del problema': cuerpo, ...} por cada encabezado '## N.'."""
    if not path.exists():
        return {}
    secciones: dict[str, list[str]] = {}
    actual: str | None = None
    for linea in path.read_text(encoding="utf-8").splitlines():
        if linea.startswith("## "):
            actual = linea[3:].strip()
            secciones[actual] = []
        elif actual is not None:
            secciones[actual].append(linea)
    return {k: "\n".join(v).strip() for k, v in secciones.items()}


def _sec(secciones: dict[str, str], num: int) -> str:
    for titulo, cuerpo in secciones.items():
        if titulo.startswith(f"{num}."):
            return cuerpo
    return "_Ver docs/alcance-contexto-proyecto.md._"


def _bullet(texto: str, clave: str) -> str | None:
    """Extrae '* **Clave:** valor...' (con sus líneas de continuación)."""
    lineas = (texto or "").splitlines()
    prefijo = f"* **{clave}:**"
    for i, ln in enumerate(lineas):
        if ln.startswith(prefijo):
            trozos = [ln[len(prefijo):]]
            for cont in lineas[i + 1:]:
                if not cont.strip() or cont.lstrip().startswith(("* ", "## ")):
                    break
                trozos.append(cont.strip())
            return " ".join(" ".join(trozos).split())
    return None


def _reglas(texto: str) -> dict[str, str]:
    """{'BR-01': 'texto...', ...} desde los bullets de §7."""
    regs: dict[str, str] = {}
    lineas = (texto or "").splitlines()
    i = 0
    while i < len(lineas):
        m = re.match(r"\* \*\*(BR-\d+):\*\*\s*(.*)", lineas[i])
        if m:
            clave, txt = m.group(1), [m.group(2)]
            j = i + 1
            while j < len(lineas) and lineas[j].strip() and not lineas[j].startswith(("* ", "## ")):
                txt.append(lineas[j].strip())
                j += 1
            regs[clave] = " ".join(" ".join(txt).split())
            i = j
        else:
            i += 1
    return regs


# ─────────────────── control humano (guía §11-§12) ───────────────────

def cargar_control(path: Path = CONTROL_PATH) -> dict:
    base = {"respuestas": {}, "estados": {}, "eventos": []}
    if path.exists():
        try:
            datos = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(datos, dict):
                return {**base, **datos}
        except (json.JSONDecodeError, OSError):
            pass
    return base


def guardar_control(control: dict, path: Path = CONTROL_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(control, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _preguntas(cuerpo: str) -> list[dict]:
    """Filas '| OPEN-Q-001 | ¿pregunta? | Responsable | Pendiente |' de §10."""
    preguntas: list[dict] = []
    for linea in (cuerpo or "").splitlines():
        if linea.strip().startswith("| OPEN-Q-"):
            partes = [p.strip() for p in linea.strip().strip("|").split("|")]
            if len(partes) >= 2:
                preguntas.append({
                    "id": partes[0],
                    "pregunta": partes[1],
                    "responsable": partes[2] if len(partes) > 2 else "Equipo",
                })
    return preguntas


def _todas_las_preguntas(alcance_path: Path = ALCANCE_PATH) -> list[dict]:
    return _preguntas(_sec(_leer_alcance(alcance_path), 10))


def _rnf_seccion(secciones: dict[str, str]) -> str:
    """Cuerpo de la §14 del alcance (RNF), o '' si el documento no la tiene."""
    cuerpo = _sec(secciones, 14)
    return "" if cuerpo.startswith("_Ver") else cuerpo


def _rnf_pendientes(secciones: dict[str, str]) -> list[str]:
    """IDs de RNF de la §14 del alcance cuyo valor sigue '[por definir]'."""
    pendientes = []
    for linea in (_rnf_seccion(secciones) or "").splitlines():
        linea = linea.strip()
        if linea.startswith("| RNF-") and "[por definir]" in linea:
            pendientes.append(linea.strip("|").split("|")[0].strip())
    return pendientes


def preguntas_generadas(num: int, secciones: dict[str, str]) -> list[dict]:
    """Preguntas que el agente propone al detectar información faltante o ambigua
    (guía §5, pasos 5-6). IDs estables para que las respuestas persistan."""
    func = next(f for f in CATALOGO if f.num == num)
    generadas: list[dict] = [
        {
            # cifras medibles por SPEC: el campo numérico de la interfaz los captura
            "id": f"SUG-{num:03d}-RNF-{m['suf']}",
            "pregunta": f"{m['ui']} de {func.nombre} — en {m['unidad_txt']}",
            "responsable": "Equipo",
            "generada": True,
            "campo": "numero",
            "unidad": m["unidad"],
        }
        for m in RNF_MODELOS
    ]
    generadas += [
        {
            "id": f"SUG-{num:03d}-CASOS",
            "pregunta": (
                f"Casos límite sin analizar (§10) para {func.nombre}. "
                "¿Qué casos deben especificarse (concurrencia, valores extremos, datos faltantes)?"
            ),
            "responsable": "Equipo",
            "generada": True,
        },
        {
            "id": f"SUG-{num:03d}-DEP",
            "pregunta": (
                f"Dependencias pendientes (§12) para {func.nombre}. "
                "¿Hay dependencias externas (datos, APIs, permisos)? Responder 'ninguna' si no aplica."
            ),
            "responsable": "Equipo",
            "generada": True,
        },
    ]
    pend_rnf = _rnf_pendientes(secciones)
    if pend_rnf:
        generadas.insert(0, {
            "id": "SUG-RNF",
            "pregunta": (
                "Valores medibles de RNF sin definir en §14 del alcance "
                "(guía §8: el agente NO debe inventar cifras): "
                f"{', '.join(pend_rnf)}. "
                "¿Cuál es el valor de cada uno (segundos, % de disponibilidad, etc.)?"
            ),
            "responsable": "Equipo",
            "generada": True,
        })
    elif not _rnf_seccion(secciones):
        generadas.insert(0, {
            "id": "SUG-RNF",
            "pregunta": (
                "El documento de alcance no tiene la §14 de requisitos no funcionales. "
                "¿Qué condiciones de calidad y valores verificables aplican al proyecto "
                "(p. ej. máximo X segundos de respuesta, Y % disponibilidad)?"
            ),
            "responsable": "Equipo",
            "generada": True,
        })
    if _bullet(_sec(secciones, 5), func.clave_alcance) is None:
        generadas.append({
            "id": f"SUG-{num:03d}-ALC",
            "pregunta": (
                f"No se encontró el alcance de '{func.clave_alcance}' en §5 del documento. "
                "¿Cuál es su alcance exacto?"
            ),
            "responsable": "Equipo",
            "generada": True,
        })
    return generadas


def _respuesta(control: dict, pregunta_id: str) -> dict | None:
    return (control.get("respuestas") or {}).get(pregunta_id)


def preguntas_pendientes(
    control: dict,
    alcance_path: Path = ALCANCE_PATH,
    spec_num: int | None = None,
) -> list[dict]:
    """Sin responder: las estáticas del alcance +, si se indica `spec_num`, las
    sugeridas por el agente para esa SPEC. Sin `spec_num`: estáticas + SUG-RNF
    (respaldo) + los RNF numéricos de las 12 SPECs."""
    respuestas = control.get("respuestas") or {}
    secciones = _leer_alcance(alcance_path)
    pend = [q for q in _preguntas(_sec(secciones, 10)) if q["id"] not in respuestas]
    if spec_num is not None:
        pend += [q for q in preguntas_generadas(spec_num, secciones) if q["id"] not in respuestas]
    else:
        pend += [q for q in preguntas_generadas(1, secciones)
                 if q["id"] == "SUG-RNF" and q["id"] not in respuestas]
        for f in CATALOGO:
            pend += [q for q in preguntas_generadas(f.num, secciones)
                     if q.get("campo") == "numero" and q["id"] not in respuestas]
    return pend


def registrar_respuesta(
    control: dict,
    pregunta_id: str,
    respuesta: str,
    responsable: str = "Equipo",
    alcance_path: Path = ALCANCE_PATH,
) -> bool:
    secciones = _leer_alcance(alcance_path)
    validos = {q["id"] for q in _preguntas(_sec(secciones, 10))}
    for f in CATALOGO:
        validos.update(q["id"] for q in preguntas_generadas(f.num, secciones))
    if pregunta_id not in validos:
        return False
    control.setdefault("respuestas", {})[pregunta_id] = {
        "respuesta": respuesta,
        "responsable": responsable,
        "fecha": datetime.date.today().isoformat(),
    }
    return True


def contexto_proyecto(alcance_path: Path = ALCANCE_PATH, control: dict | None = None) -> str:
    """Contexto para el LLM del generador de historias, construido desde el
    documento de alcance (fuente única de verdad) en lugar de texto hardcodeado.

    Incluye §1 problema, §2 solución, §3 objetivos, §4 público, §5 alcances,
    §6 fuera de alcance, §7 reglas de negocio, §8 priorización, §9 roles y la §14
    de RNF (solo las filas cuyo valor ya está decidido), más las decisiones
    humanas ya resueltas (control.json). Excluye §10 preguntas abiertas y §11-§13
    (entregables, equipo/plazo, párrafo de contexto): las decisiones pendientes
    no se le pasan al modelo (guía §8: no debe inventar valores). ~4.7 KB, seguro
    para la ventana de 8192 tokens de qwen2.5:3b."""
    secciones = _leer_alcance(alcance_path)
    if not secciones:
        return ""
    if control is None:
        control = cargar_control()
    cuerpo_rnf = ""
    if _rnf_seccion(secciones):
        lineas = [
            ln for ln in _rnf_seccion(secciones).splitlines()
            if "[por definir]" not in ln and not ln.lstrip().startswith(">")
        ]
        cuerpo_rnf = "\n".join(lineas).strip()
        if "| RNF-" not in cuerpo_rnf:
            cuerpo_rnf = ""          # ningún valor decidido todavía: no se filtra
    bloques = [
        ("PROBLEMA", _sec(secciones, 1)),
        ("SOLUCIÓN", _sec(secciones, 2)),
        ("OBJETIVOS", _sec(secciones, 3)),
        ("PÚBLICO OBJETIVO", _sec(secciones, 4)),
        ("ALCANCES — SOLO ESTAS FUNCIONALIDADES", _sec(secciones, 5)),
        ("FUERA DE ALCANCE — NUNCA INVENTES NADA DE ESTO", _sec(secciones, 6)),
        ("REGLAS DE NEGOCIO — RESPÉTALAS EN FLUJOS Y CRITERIOS", _sec(secciones, 7)),
        ("PRIORIZACIÓN", _sec(secciones, 8)),
        ("ROLES", _sec(secciones, 9)),
        ("REQUISITOS NO FUNCIONALES — SOLO VALORES YA DECIDIDOS, NO INVENTES LOS QUE FALTEN",
         cuerpo_rnf),
    ]
    partes = [
        f"[{titulo}]\n{cuerpo.strip()}"
        for titulo, cuerpo in bloques
        if cuerpo and not cuerpo.startswith("_Ver")
    ]
    respuestas = control.get("respuestas") or {}
    if respuestas:
        decisiones = "\n".join(
            f"- {pid}: {r.get('respuesta', '')} ({r.get('responsable', '?')}, {r.get('fecha', '?')})"
            for pid, r in sorted(respuestas.items())
        )
        partes.append(
            "[DECISIONES YA TOMADAS POR EL EQUIPO — NO LAS CONTRADIGAS]\n" + decisiones
        )
    return "\n\n".join(partes)


def _info_secciones(markdown: str) -> dict[str, tuple[str, str]]:
    """{num_sección: (título, sha256(título+cuerpo))} para §1..§16 (cabecera y §17 excluidas)."""
    info: dict[str, tuple[str, str]] = {}
    patron = re.compile(r"(?m)^## (\d+)\. ([^\n]+)\n(.*?)(?=^## \d+\. |\Z)", re.S)
    for m in patron.finditer(markdown):
        num, titulo, cuerpo = m.group(1), m.group(2).strip(), m.group(3)
        if num == "17":
            continue
        digesto = hashlib.sha256(f"{titulo}\n{cuerpo}".encode("utf-8")).hexdigest()
        info[num] = (titulo, digesto)
    return info


def _bump(version: str) -> str:
    partes = str(version).split(".")
    if len(partes) == 2 and partes[1].isdigit():
        return f"{partes[0]}.{int(partes[1]) + 1}"
    return version


def detectar_cambios(control: dict, docs: list[SpecDoc]) -> list[str]:
    """§2.8 (gestión de cambios): si el contenido de una SPEC aprobada/congelada ya no
    coincide con el aprobado, sube la versión, la devuelve a borrador (re-aprobación
    humana) y registra el impacto en el historial. Devuelve mensajes de log."""
    mensajes: list[str] = []
    for d in docs:
        est = (control.get("estados") or {}).get(f"{d.num:03d}")
        if not est or est.get("estado") not in ("aprobada", "congelada"):
            continue
        actuales = _info_secciones(d.markdown)
        hashes_actuales = {k: v[1] for k, v in actuales.items()}
        guardadas = est.get("hashes")
        if not guardadas:
            est["hashes"] = hashes_actuales            # respaldo de aprobaciones antiguas
            continue
        distintas = sorted(
            (k for k in set(guardadas) | set(hashes_actuales)
             if guardadas.get(k) != hashes_actuales.get(k)),
            key=int,
        )
        if not distintas:
            continue
        impacto = ", ".join(
            f"§{k} {actuales[k][0]}" if k in actuales else f"§{k} (sección eliminada)"
            for k in distintas
        )
        nueva = _bump(est.get("version", "1.0"))
        est.update(
            estado="borrador",
            version=nueva,
            hashes=hashes_actuales,
        )
        control.setdefault("eventos", []).append({
            "spec": f"{d.num:03d}",
            "evento": "Cambio detectado",
            "fecha": datetime.date.today().isoformat(),
            "version": nueva,
            "impacto": impacto,
        })
        mensajes.append(
            f"SPEC-{d.num:03d}: cambio detectado ({impacto}) → v{nueva} pendiente de re-aprobación."
        )
    return mensajes


def aprobar(
    control: dict,
    num: int,
    por: str,
    alcance_path: Path = ALCANCE_PATH,
    markdown: str | None = None,
) -> tuple[bool, str]:
    pend = preguntas_pendientes(control, alcance_path, spec_num=num)
    if pend:
        ids = ", ".join(q["id"] for q in pend)
        return False, f"No se puede aprobar: faltan respuestas a {ids} (guía §12: detener el cierre)."
    clave = f"{num:03d}"
    est = control.setdefault("estados", {}).get(clave)
    if est and est.get("estado") in ("aprobada", "congelada"):
        return False, f"SPEC-{clave} ya está {est.get('estado')}."
    hoy = datetime.date.today().isoformat()
    version = "1.0"
    if est and est.get("version") and est["version"] != "0.1":
        version = est["version"]          # re-aprobación tras un cambio: conserva v1.x
    nuevo = {"estado": "aprobada", "version": version, "por": por, "fecha": hoy}
    if markdown is not None:
        nuevo["hashes"] = {k: v[1] for k, v in _info_secciones(markdown).items()}
    elif est and est.get("hashes"):
        nuevo["hashes"] = est["hashes"]
    control["estados"][clave] = nuevo
    control.setdefault("eventos", []).append(
        {"spec": clave, "evento": "Aprobada", "por": por, "fecha": hoy, "version": version}
    )
    return True, f"SPEC-{clave} APROBADA v{version} por {por}."


def congelar(control: dict, num: int) -> tuple[bool, str]:
    clave = f"{num:03d}"
    est = control.setdefault("estados", {}).get(clave)
    if not est or est.get("estado") != "aprobada":
        return False, f"SPEC-{clave} no está aprobada: primero apruébala (guía §12)."
    hoy = datetime.date.today().isoformat()
    est["estado"] = "congelada"
    control.setdefault("eventos", []).append(
        {"spec": clave, "evento": "Congelada", "fecha": hoy, "version": est.get("version", "1.0")}
    )
    return True, f"SPEC-{clave} FROZEN v{est.get('version', '1.0')}."


def interactivo_responder(
    control: dict,
    alcance_path: Path = ALCANCE_PATH,
    spec_num: int | None = None,
) -> dict:
    pendientes = preguntas_pendientes(control, alcance_path, spec_num)
    if not pendientes:
        print("No hay preguntas pendientes.", flush=True)
        return control
    for q in pendientes:
        etq = "sugerida por el agente" if q.get("generada") else f"responsable sugerido: {q['responsable']}"
        print(f"\n{q['id']} ({etq})", flush=True)
        print(f"  {q['pregunta']}", flush=True)
        resp = input("  Respuesta (Enter = omitir): ").strip()
        if resp:
            quien = input("  ¿Quién responde? [Equipo]: ").strip() or "Equipo"
            registrar_respuesta(control, q["id"], resp, quien, alcance_path)
    return control


def _md_preguntas(secciones: dict[str, str], control: dict, num: int) -> str:
    cuerpo = _sec(secciones, 10)
    respuestas = control.get("respuestas") or {}

    def _fila(q: dict) -> str:
        r = respuestas.get(q["id"])
        if r:
            return (
                f"- **{q['id']}** — **Respondida** "
                f"({r.get('responsable', '?')}, {r.get('fecha', '?')}): {r.get('respuesta', '')}"
            )
        etiqueta = " (sugerida por el agente)" if q.get("generada") else ""
        return f"- **{q['id']}** — **Pendiente**{etiqueta}: {q['pregunta']}"

    lineas = [cuerpo, "", "**Estado de cada pregunta (control humano):**", ""]
    lineas.extend(_fila(q) for q in _preguntas(cuerpo))
    generadas = preguntas_generadas(num, secciones)
    if generadas:
        lineas += ["", "**Preguntas sugeridas por el agente (§5 pasos 5-6):**", ""]
        lineas.extend(_fila(q) for q in generadas)
    return "\n".join(lineas)


# ───────────────────────── ensamblado de la SPEC ─────────────────────────

def _tema_de(rol: str, indice: int) -> str:
    base = TEMAS_POR_ROL[rol]
    return base[indice % len(base)]


def _construir_markdown(
    func: Funcionalidad,
    asignadas: list[tuple[str, int, object]],  # (rol, indice, historia)
    secciones: dict[str, str],
    control: dict,
) -> str:
    fecha = datetime.date.today().isoformat()
    reglas = _reglas(_sec(secciones, 7))
    n = func.num
    actores = ", ".join(func.actores)

    clave = f"{n:03d}"
    est = (control.get("estados") or {}).get(clave, {})
    estado = est.get("estado", "borrador")
    if estado == "aprobada":
        version = est.get("version", "1.0")
        estado_txt = f"APROBADA v{version} — aprobada por {est.get('por', '?')}, {est.get('fecha', '?')}"
    elif estado == "congelada":
        version = est.get("version", "1.0")
        estado_txt = f"FROZEN (congelada) v{version} — cambios requieren nueva versión"
    else:
        estado = "borrador"
        version = est.get("version", "0.1")
        if version != "0.1":
            estado_txt = (
                f"Borrador v{version} — pendiente de re-aprobación "
                f"(última aprobación: {est.get('por', '?')}, {est.get('fecha', '?')})"
            )
        else:
            estado_txt = "Borrador v0.1 — pendiente de aprobación humana"

    cabecera = (
        f"# SPEC-{n:03d} — {func.nombre}\n\n"
        "| Campo | Valor |\n|-------|-------|\n"
        f"| Versión | {version} |\n"
        f"| Estado | {estado_txt} |\n"
        f"| Funcionalidad | {func.nombre} |\n"
        f"| Actores | {actores} |\n"
        f"| Generado | {fecha} (automático) |\n\n"
        "> Fuente: `docs/alcance-contexto-proyecto.md` + historias de usuario generadas.\n"
        "> Estructura según la sección 7 de la guía del Specification Agent.\n"
    )

    # §5 Requisitos funcionales (de las historias)
    rf_lineas: list[str] = []
    ac_lineas: list[str] = []
    flujo_norm: list[str] = []
    flujo_alt: list[str] = []
    limite: list[str] = []
    traza: list[str] = []
    ac_seq = 0
    for rf_seq, (rol, indice, h) in enumerate(asignadas, start=1):
        rf_id = f"RF-{n:03d}-{rf_seq:02d}"
        rf_lineas.append(f"- **{rf_id}** [{h.id}] Como {h.como}, quiero {h.quiero}, para {h.para}.")
        flujo_norm.append(f"- **{h.id}:** {' → '.join(h.flujo_normal)}")
        flujo_alt.append(f"- **{h.id} (alternativo):** {' → '.join(h.flujo_alternativo)}")
        flujo_alt.append(f"- **{h.id} (excepción):** {' → '.join(h.flujo_excepcion)}")
        limite.extend(f"- **{h.id}:** {paso}"
                      for paso in (*h.flujo_alternativo, *h.flujo_excepcion))
        ac_ids = []
        for j, c in enumerate(h.criterios, start=1):
            ac_seq += 1
            ac_id = f"AC-{n:03d}-{ac_seq:02d}"
            ac_ids.append(ac_id)
            ac_lineas.append(f"- **{ac_id}** [{h.id}.CA-{j}] {c.texto}")
        traza.append(f"| {h.id} | {rf_id} | {', '.join(ac_ids)} | {_tema_de(rol, indice)} |")

    if not asignadas:
        pendiente_hist = "> **Pendiente:** sin historias asignadas en la corrida actual. Genere historias (app o CLI) y vuelva a exportar."
        rf_lineas = [pendiente_hist]
        ac_lineas = [pendiente_hist]
        flujo_norm = [pendiente_hist]
        flujo_alt = [pendiente_hist]
        limite = [pendiente_hist]
        traza = []

    traza_md = (
        "| Historia | Requisito | Criterios | Tema |\n|----------|-----------|-----------|------|\n"
        + "\n".join(traza)
        if traza
        else "> **Pendiente:** sin historias para trazar."
    )

    br_md = "\n".join(
        f"- **{clave}:** {reglas[clave]}" if clave in reglas else f"- **{clave}:** _Ver §7 del documento de alcance._"
        for clave in func.brs
    )
    alcance_func = _bullet(_sec(secciones, 5), func.clave_alcance)

    # §6:3 RNF medibles por SPEC (guía §2.2/§8) que el equipo define en §15 +
    # las filas fijas (seguridad/integridad/compatibilidad) de la §14 del alcance
    r_rnf = _respuesta(control, "SUG-RNF")
    filas_rnf: list[str] = []
    sin_valor: list[str] = []
    for m in RNF_MODELOS:
        rid = f"RNF-{n:03d}-{m['suf']}"
        qid = f"SUG-{n:03d}-RNF-{m['suf']}"
        r = _respuesta(control, qid)
        valor = r["respuesta"] if r else "[por definir]"
        if r:
            celda = (f"**{valor} {m['unidad']}** "
                     f"({r.get('responsable', '?')}, {r.get('fecha', '?')})")
        else:
            celda = "**[por definir]**"
            sin_valor.append(qid)
        requisito = m["req"].format(
            op=RNF_OPERACION[n], opde=_de(RNF_OPERACION[n]), valor=valor
        )
        filas_rnf.append(f"| {rid} | {m['categoria']} | {requisito} | {celda} |")
    filas_fijas = [
        ln.strip() for ln in (_rnf_seccion(secciones) or "").splitlines()
        if ln.strip().startswith("| RNF-")
    ]
    md6 = (
        "> Valores medibles por funcionalidad, definidos por el equipo en §15 "
        "(guía §8: el agente no inventa cifras). Las filas fijas de seguridad, "
        "integridad y compatibilidad vienen de "
        "`docs/alcance-contexto-proyecto.md` §14.\n\n"
        "| ID | Categoría | Requisito verificable | Valor |\n"
        "|----|-----------|----------------------|-------|\n"
        + "\n".join(filas_rnf + filas_fijas)
    )
    if sin_valor:
        md6 += (
            f"\n\nValores **[por definir]** → decisiones abiertas en §15: "
            f"{', '.join(sin_valor)}."
        )
    if r_rnf:  # respaldo: pregunta global SUG-RNF si el alcance la planteó
        md6 += (
            f"\n\n**Valores globales definidos por el equipo "
            f"({r_rnf.get('responsable', '?')}, {r_rnf.get('fecha', '?')}):** "
            f"{r_rnf.get('respuesta', '')}"
        )
    r_casos = _respuesta(control, f"SUG-{n:03d}-CASOS")
    md10_cierre = (
        f"**Casos límite definidos por el equipo ({r_casos.get('responsable', '?')}, "
        f"{r_casos.get('fecha', '?')}):** {r_casos.get('respuesta', '')}"
        if r_casos else
        "- Casos límite adicionales (concurrencia, valores extremos): **pendiente de análisis** (guía §2.6)."
    )
    r_dep = _respuesta(control, f"SUG-{n:03d}-DEP")
    md12 = (
        f"**Dependencias (respuesta de {r_dep.get('responsable', '?')}, {r_dep.get('fecha', '?')}):** "
        f"{r_dep.get('respuesta', '')}"
        if r_dep else
        "> **Pendiente:** corresponde a la etapa de arquitectura, no definida en este documento."
    )

    md15 = _md_preguntas(secciones, control, n)
    if estado == "borrador":
        aprob_col = "Pendiente (re-aprobación)" if version != "0.1" else "Pendiente (humana)"
    else:
        aprob_col = {"aprobada": "APROBADA", "congelada": "FROZEN"}[estado]
    filas_hist = [
        f"| {version} | {fecha} | Generación automática desde alcance + historias | {aprob_col} |"
    ]
    for ev in control.get("eventos") or []:
        if str(ev.get("spec")) == clave:
            detalle = ev.get("evento", "")
            if ev.get("por"):
                detalle += f" por {ev['por']}"
            if ev.get("impacto"):
                detalle += f" — impacto: {ev['impacto']}"
            aprob_ev = {
                "Aprobada": "APROBADA",
                "Congelada": "FROZEN",
                "Cambio detectado": "Pendiente (re-aprobación)",
            }.get(ev.get("evento", ""), "")
            filas_hist.append(
                f"| {ev.get('version', version)} | {ev.get('fecha', '')} | {detalle} | {aprob_ev} |"
            )
    historial = "\n".join(filas_hist)

    return f"""{cabecera}
## 1. Objetivo
{func.objetivo}

## 2. Contexto
{_sec(secciones, 1)}

{_sec(secciones, 2)}

## 3. Alcance
{f"- {alcance_func}" if alcance_func else "_Ver §5 de docs/alcance-contexto-proyecto.md._"}

Ver también **Fuera de alcance** (§14 de esta SPEC).

## 4. Actores
{chr(10).join(f'- **{a}**' for a in func.actores)}

## 5. Requisitos funcionales
{chr(10).join(rf_lineas)}

## 6. Requisitos no funcionales
{md6}

## 7. Reglas de negocio
{br_md}

## 8. Flujos principales
{chr(10).join(flujo_norm)}

## 9. Flujos alternativos
{chr(10).join(flujo_alt)}

## 10. Casos límite
{chr(10).join(limite)}
{md10_cierre}

## 11. Criterios de aceptación
{chr(10).join(ac_lineas)}

## 12. Dependencias
{md12}

## 13. Restricciones
{_sec(secciones, 12)}

## 14. Fuera de alcance
{_sec(secciones, 6)}

## 15. Preguntas abiertas
{md15}

## 16. Trazabilidad
{traza_md}

## 17. Historial de cambios
| Versión | Fecha | Cambio | Aprobación |
|---------|-------|--------|------------|
{historial}
"""


def construir_specs(
    historias: HistoriasGeneradas | None = None,
    alcance_path: Path = ALCANCE_PATH,
    control: dict | None = None,
) -> list[SpecDoc]:
    """Arma las 12 SPECs. `historias=None` genera esqueletos con §8/§9/§11/§16 pendientes.
    `control=None` carga el estado humano desde CONTROL_PATH (si existe)."""
    secciones = _leer_alcance(alcance_path)
    if control is None:
        control = cargar_control()

    asignadas: dict[int, list[tuple[str, int, object]]] = {f.num: [] for f in CATALOGO}
    if historias is not None:
        for rol, lista in (
            ("pasajero", historias.pasajero),
            ("conductor", historias.conductor),
            ("administrador", historias.administrador),
        ):
            for i, h in enumerate(lista):
                asignadas[spec_de_historia(rol, i)].append((rol, i, h))

    docs: list[SpecDoc] = []
    for func in CATALOGO:
        docs.append(
            SpecDoc(
                num=func.num,
                slug=func.slug,
                nombre=func.nombre,
                markdown=_construir_markdown(func, asignadas[func.num], secciones, control),
            )
        )
    return docs


def escribir_specs(docs: list[SpecDoc], carpeta: Path | str = SPECS_DIR) -> list[Path]:
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = []
    for d in docs:
        ruta = carpeta / d.nombre_archivo
        ruta.write_text(d.markdown, encoding="utf-8")
        rutas.append(ruta)
    return rutas


def seleccionar(docs: list[SpecDoc], valor: str) -> list[SpecDoc]:
    """Filtra por 'all', número (3, 003), slug (rutas) o nombre (substring)."""
    v = valor.strip().lower().replace(" ", "-")
    if v in ("all", "*", ""):
        return docs
    elegidos = [
        d for d in docs
        if v in (d.slug, str(d.num), f"{d.num:03d}", f"spec-{d.num:03d}", d.nombre.lower().replace(" ", "-"))
        or v in d.slug
        or v in d.nombre.lower()
    ]
    return elegidos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Genera las 12 SPECs (17 secciones, guía §7) desde el documento de alcance."
    )
    ap.add_argument("--historias", help="JSON de historias exportado con CLI --json (opcional)")
    ap.add_argument("--spec", default="all", help="Todas (default) o un número/slug (ej. 003, rutas)")
    ap.add_argument("--out", default=str(SPECS_DIR), help="Carpeta de salida (default: docs/specs)")
    ap.add_argument("--control", default=None, help=f"Archivo de control humano (default: {CONTROL_PATH})")
    ap.add_argument("--responder", nargs="?", const="all", default=None, metavar="SPEC",
                    help="Responde en consola las preguntas pendientes: sin valor = globales; "
                         "con SPEC (ej. 001) = también las sugeridas de esa SPEC")
    ap.add_argument("--aprobar", metavar="SPEC",
                    help="Aprueba una SPEC (001 o slug); se niega si hay preguntas pendientes")
    ap.add_argument("--congelar", metavar="SPEC",
                    help="Pasa una SPEC aprobada a FROZEN (congelada)")
    ap.add_argument("--por", default=None, help="Nombre de quién aprueba (para --aprobar)")
    args = ap.parse_args(argv)

    historias: HistoriasGeneradas | None = None
    if args.historias:
        texto = Path(args.historias).read_text(encoding="utf-8")
        historias = HistoriasGeneradas.model_validate_json(texto)

    control_path = Path(args.control) if args.control else CONTROL_PATH
    control = cargar_control(control_path)
    accion_ok = True
    hubo_cambios = False

    def _resolver_num(valor: str) -> int | None:
        mini = [SpecDoc(f.num, f.slug, f.nombre, "") for f in CATALOGO]
        sel = seleccionar(mini, valor)
        if len(sel) != 1:
            print(f"'{valor}' coincide con {len(sel)} SPECs; usa un número o slug exacto (ej. 001).",
                  flush=True)
            return None
        return sel[0].num

    if args.responder is not None:
        spec_num = None
        if args.responder != "all":
            spec_num = _resolver_num(args.responder)
            if spec_num is None:
                return 1
        control = interactivo_responder(control, spec_num=spec_num)
        hubo_cambios = True

    # §2.8: detectar cambios en SPECs aprobadas/congeladas antes de continuar
    docs_all = construir_specs(historias, control=control)
    mensajes = detectar_cambios(control, docs_all)
    if mensajes:
        for m in mensajes:
            print(m, flush=True)
        hubo_cambios = True
        docs_all = construir_specs(historias, control=control)

    if args.aprobar:
        num = _resolver_num(args.aprobar)
        if num is None:
            accion_ok = False
        else:
            doc = next((d for d in docs_all if d.num == num), None)
            ok, msg = aprobar(
                control, num, args.por or "Humano",
                markdown=doc.markdown if doc else None,
            )
            print(msg, flush=True)
            accion_ok = accion_ok and ok
            hubo_cambios = hubo_cambios or ok

    if args.congelar:
        num = _resolver_num(args.congelar)
        if num is None:
            accion_ok = False
        else:
            ok, msg = congelar(control, num)
            print(msg, flush=True)
            accion_ok = accion_ok and ok
            hubo_cambios = hubo_cambios or ok

    if hubo_cambios:
        guardar_control(control, control_path)
        print(f"Control guardado en {control_path}", flush=True)
        docs_all = construir_specs(historias, control=control)

    docs = seleccionar(docs_all, args.spec)
    if not docs:
        print(f"Ninguna SPEC coincide con '{args.spec}'.", flush=True)
        return 1
    rutas = escribir_specs(docs, args.out)
    for r in rutas:
        print(r, flush=True)
    print(f"{len(rutas)} SPEC(s) escritas en {args.out}", flush=True)
    return 0 if accion_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

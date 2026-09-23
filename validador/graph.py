# Docstring del módulo: describe el ensamblado del grafo LangGraph con nodos,
# aristas condicionales y paralelismo controlado.
# Sintaxis: triple comilla doble. El diagrama ASCII muestra el flujo completo.
# Lógica: este archivo es el "cerebro" del sistema. Conecta todos los nodos
# (prevalidar, analizar, invest, ambigüedad, etc.) con aristas que deciden
# a qué nodo ir según el resultado del nodo actual.
"""Ensamblado del grafo: nodos + aristas condicionales + paralelismo controlado.

START → prevalidar ─┬─(bloqueada)──────────────────────────────────► finalizar
                    └─► relevancia ─┬─(no relevante)───────────────► finalizar
                                   └─► analizar ─┬─(no es HU / error)──► finalizar
                                                 └─► [invest ∥ ambiguedad] ─► puntuar
        puntuar ─┬─(requiere_reescritura)─► reescribir ─► criterios ─► finalizar
                 └─(aprobada / observaciones)─► criterios ─┬─(aprobada)──────► finalizar
                                                           └─(observaciones)─► reescribir ─► finalizar
"""
from __future__ import annotations  # Anotaciones de tipo diferidas (PEP 563)

from langgraph.graph import END, START, StateGraph  # LangGraph: grafo de estados con LangChain

from .chains import build_chains          # Crea las cadenas LLM (prompt | modelo | validador)
from .config import Settings, get_settings  # Configuración del sistema
from .llm import build_providers          # Crea los proveedores LLM (Gemini, Ollama)
from .nodes import make_nodes             # Crea las funciones de cada nodo del grafo
from .state import GraphState, InputState, OutputState  # Tipos de estado del grafo


# ───────────── Funciones de ruteo (deciden el siguiente nodo) ─────────────

# route_after_prevalidation: decide si la historia pasa a relevancia o se rechaza.
# Sintaxis: recibe el estado del grafo, retorna un string con el nombre del siguiente nodo.
# Lógica: si prevalidation.ok es True, la historia tiene formato válido y sigue a "relevancia".
# Si no, tiene errores bloqueadores y va directo a "finalizar" (rechazada).
def route_after_prevalidation(state: GraphState) -> str:
    return "relevancia" if state["prevalidation"].ok else "finalizar"


# route_after_relevance: decide después de verificar la relevancia.
# Sintaxis: recibe el estado, retorna string.
# Lógica: si la historia no es relevante para el proyecto, va a "finalizar" (no_relevante).
# Si es relevante, sigue a "analizar" para descomponer la historia.
def route_after_relevance(state: GraphState) -> str:
    rel = state.get("relevance")
    if not rel or not rel.es_relevante:
        return "finalizar"
    return "analizar"


# route_after_analysis: decide después del análisis LLM.
# Sintaxis: recibe el estado, retorna string o lista de strings.
# Lógica: si hay errores, o el análisis no existe, o el LLM dijo que no es
# historia de usuario → va a "finalizar". Si todo está bien → lanza invest
# y ambigüedad EN PARALELO (fan-out con lista de dos elementos).
def route_after_analysis(state: GraphState):
    if state.get("errors") or not state.get("analysis") or not state["analysis"].es_historia_usuario:
        return "finalizar"
    return ["invest", "ambiguedad"]  # fan-out: se ejecutan en paralelo


# _failed: helper que verifica si un nodo específico falló.
# Sintaxis: recibe el estado y el nombre del nodo, retorna bool.
# Lógica: busca en la lista de errores si alguno empieza con "nombre_nodo:".
# Si encuentra, significa que ese nodo falló y su error quedó registrado.
def _failed(state: GraphState, node: str) -> bool:
    return any(e.startswith(f"{node}:") for e in state.get("errors", []))


# route_after_score: decide después de calcular el puntaje INVEST.
# Sintaxis: recibe el estado, retorna string.
# Lógica: si preliminary_verdict no existe, significa que invest o ambigüedad
# fallaron → "finalizar". Si el veredicto es "requiere_reescritura" → "reescribir".
# Si es "aprobada" o "aprobada_con_observaciones" → "criterios".
def route_after_score(state: GraphState) -> str:
    if "preliminary_verdict" not in state:  # INVEST o Ambigüedad fallaron
        return "finalizar"
    return "reescribir" if state["preliminary_verdict"] == "requiere_reescritura" else "criterios"


# route_after_criteria: decide después de generar criterios de aceptación.
# Sintaxis: recibe el estado, retorna string.
# Lógica: si el veredicto es "aprobada_con_observaciones" Y no existe reescritura
# aún, la historia necesita mejoras → "reescribir". Si ya se reescribió o el
# veredicto es "aprobada" → "finalizar". Esto evita ciclos infinitos.
def route_after_criteria(state: GraphState) -> str:
    # Evita ciclos: solo reescribe si aún no existe una reescritura.
    if state.get("preliminary_verdict") == "aprobada_con_observaciones" and not state.get("rewrite"):
        return "reescribir"
    return "finalizar"


# route_after_rewrite: decide después de reescribir la historia.
# Sintaxis: recibe el estado, retorna string.
# Lógica: si no existen criterios Y el nodo "criterios" no falló, genera
# criterios sobre la historia MEJORADA (solo una vez). Si ya existen o
# fallaron → "finalizar".
def route_after_rewrite(state: GraphState) -> str:
    # Tras reescribir, genera criterios sobre la historia mejorada (solo una vez).
    if not state.get("criteria") and not _failed(state, "criterios"):
        return "criterios"
    return "finalizar"


# build_graph: construye y compila el grafo completo de validación.
# Sintaxis: recibe chains (cadenas LLM) y settings opcionales. Retorna el grafo compilado.
# Lógica: 1) Crea los proveedores LLM (Gemini, Ollama).
#         2) Crea las cadenas LLM (prompt | modelo | validador).
#         3) Crea los nodos (funciones de cada paso).
#         4) Define las conexiones entre nodos (aristas).
#         5) Compila el grafo para que sea ejecutable.
def build_graph(chains: dict | None = None, settings: Settings | None = None):
    """Compila el grafo. Puedes inyectar `chains` falsas para pruebas sin LLM."""
    s = settings or get_settings()  # Usa settings pasados o los del .env

    # Si no se pasan cadenas, crea las reales con los proveedores LLM
    if chains is None:
        chains = build_chains(build_providers(s))

    # Crea los nodos del grafo (prevalidar, analizar, invest, etc.)
    nodes = make_nodes(chains, s)

    # Crea el StateGraph con el tipo de estado y los schemas de entrada/salida
    g = StateGraph(GraphState, input_schema=InputState, output_schema=OutputState)

    # Registra cada nodo en el grafo: nombre -> función
    for name, fn in nodes.items():
        g.add_node(name, fn)

    # ──────── Conexiones del grafo (aristas) ────────

    # START → prevalidar: el grafo siempre empieza en prevalidar
    g.add_edge(START, "prevalidar")

    # prevalidar → relevancia | finalizar: según si la prevalidación pasó
    g.add_conditional_edges("prevalidar", route_after_prevalidation, ["relevancia", "finalizar"])

    # relevancia → analizar | finalizar: según si la historia es relevante
    g.add_conditional_edges("relevancia", route_after_relevance, ["analizar", "finalizar"])

    # analizar → invest + ambiguedad | finalizar: según si es historia de usuario
    g.add_conditional_edges("analizar", route_after_analysis, ["invest", "ambiguedad", "finalizar"])

    # invest + ambiguedad → puntuar: JOIN (espera a que AMBOS terminen)
    g.add_edge(["invest", "ambiguedad"], "puntuar")  # join: espera a ambos

    # puntuar → reescribir | criterios | finalizar: según el veredicto
    g.add_conditional_edges("puntuar", route_after_score, ["reescribir", "criterios", "finalizar"])

    # criterios → reescribir | finalizar: según si necesita mejoras
    g.add_conditional_edges("criterios", route_after_criteria, ["reescribir", "finalizar"])

    # reescribir → criterios | finalizar: genera criterios sobre la historia mejorada
    g.add_conditional_edges("reescribir", route_after_rewrite, ["criterios", "finalizar"])

    # finalizar → END: el grafo termina aquí
    g.add_edge("finalizar", END)

    # Compila el grafo: convierte la definición en un ejecutable
    return g.compile()

# state.py: Define el estado del grafo LangGraph.
# Lógica: el grafo es un sistema de nodos que comparten un estado.
# Cada nodo lee de este estado y escribe SOLO las llaves que le corresponden.
# Los reducers (Annotated con operator.add) permiten que múltiples nodos
# escriban en la misma lista SIN sobrescribirse (se acumulan).

"""Estado del grafo con anotaciones (reducers) para nodos que escriben en paralelo."""
from __future__ import annotations  # Anotaciones de tipo diferidas (PEP 563)

import operator  # Operadores como funciones (para reducers)

# Annotated: agrega metadata al tipo (ej: reducer).
# Literal: tipo que solo acepta valores específicos.
# NotRequired: campo opcional en TypedDict.
# TypedDict: diccionario con tipos estáticos para cada llave.
from typing import Annotated, Literal, NotRequired, TypedDict

from .schemas import (  # Modelos Pydantic que definen la estructura de cada dato
    AcceptanceCriteria,
    AmbiguityReport,
    FinalResult,
    InvestEvaluation,
    Prevalidation,
    RelevanceResult,
    RewriteSuggestion,
    StoryAnalysis,
)


# TraceEntry: entrada individual de la traza de ejecución.
# Lógica: cada nodo agrega una entrada con su nombre, estado, tiempo y detalle.
class TraceEntry(TypedDict):
    node: str                           # Nombre del nodo (ej: "prevalidar")
    status: Literal["ok", "error", "skipped"]  # Estado de la ejecución
    ms: int                             # Tiempo de ejecución en milisegundos
    detail: str                         # Detalle adicional (error o info)


# InputState: lo que el usuario DEBE entregar al grafo.
# Sintaxis: TypedDict con total=True (campos obligatorios por defecto).
# Lógica: solo necesita la historia cruda. El contexto es opcional.
class InputState(TypedDict):
    """Lo único que el usuario debe entregar al grafo."""

    raw_story: str                      # Historia de usuario en texto plano (obligatorio)
    project_context: NotRequired[str]   # Contexto del proyecto (opcional)


# OutputState: lo que el grafo devuelve al terminar.
# Lógica: solo retorna el resultado final y la traza completa.
class OutputState(TypedDict):
    """Lo único que el grafo devuelve al terminar."""

    result: FinalResult                 # Resultado estructurado con todo
    trace: list[TraceEntry]             # Traza de ejecución de todos los nodos


# GraphState: el estado COMPLETO del grafo (hereda de InputState).
# Sintaxis: total=False significa que todos los campos son opcionales por defecto.
# Lógica: cada nodo escribe SOLO las llaves que le corresponden.
# Los campos con Annotated[list[...], operator.add] son REDUCERS:
# si múltiples nodos escriben en la misma llave, los valores se ACUMULAN
# (no se sobrescriben). Esto es necesario para errores, proveedores y traza.
class GraphState(InputState, total=False):
    # ── Salidas de cada nodo ──
    prevalidation: Prevalidation       # Nodo "prevalidar" escribe aquí
    relevance: RelevanceResult         # Nodo "relevancia" escribe aquí
    analysis: StoryAnalysis             # Nodo "analizar" escribe aquí
    invest: InvestEvaluation            # Nodo "invest" escribe aquí
    ambiguity: AmbiguityReport          # Nodo "ambiguedad" escribe aquí
    criteria: AcceptanceCriteria        # Nodo "criterios" escribe aquí
    rewrite: RewriteSuggestion          # Nodo "reescribir" escribe aquí

    # ── Decisiones deterministas (Python puro, sin LLM) ──
    invest_score: float                 # Promedio INVEST calculado en "puntuar"
    preliminary_verdict: str            # Veredicto determinista calculado en "puntuar"

    # ── Reducers: se ACUMULAN aunque los nodos corran en paralelo ──
    # operator.add: si dos nodos escriben en la lista, se concatenan.
    # Ejemplo: si "invest" agrega ["openai"] y "ambiguedad" agrega ["ollama"],
    # el resultado es ["openai", "ollama"].
    errors: Annotated[list[str], operator.add]          # Errores acumulados
    providers: Annotated[list[str], operator.add]       # Proveedores LLM usados
    trace: Annotated[list[TraceEntry], operator.add]    # Traza de ejecución

    # ── Resultado final ──
    result: FinalResult                 # Nodo "finalizar" escribe aquí

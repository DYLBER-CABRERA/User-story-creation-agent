# Docstring del módulo: describe que este archivo crea cadenas LCEL
# (LangChain Expression Language) con retry y fallback entre proveedores.
# Sintaxis: triple comilla doble.
# Lógica: cada cadena conecta un prompt + un LLM + un validador de salida.
# Si el LLM falla, reintenta 1 vez. Si sigue fallando, pasa al siguiente proveedor.
"""Cadenas LCEL: prompt | modelo estructurado, con reintento y respaldo entre proveedores."""
from __future__ import annotations  # Anotaciones de tipo diferidas (PEP 563)

from typing import Any, NamedTuple  # Any: tipo comodín. NamedTuple: tupla con campos con nombre.

from langchain_core.exceptions import OutputParserException  # Excepción cuando el LLM no respeta el esquema Pydantic
from langchain_core.language_models.chat_models import BaseChatModel  # Clase base de modelos de chat en LangChain
from langchain_core.prompts import ChatPromptTemplate  # Plantilla de prompts para chats
from langchain_core.runnables import Runnable, RunnableLambda  # Runnable: cadena ejecutable. RunnableLambda: envuelve funciones.
from pydantic import BaseModel, ValidationError  # BaseModel: modelos de datos. ValidationError: error de validación.

from . import prompts  # Importa el módulo de prompts (ANALYSIS_PROMPT, INVEST_PROMPT, etc.)
from .schemas import (  # Importa los esquemas Pydantic que el LLM debe devolver
    AcceptanceCriteria,
    AmbiguityReport,
    InvestEvaluation,
    RelevanceResult,
    RewriteSuggestion,
    StoryAnalysis,
)


# Tagged: tupla con nombre que empaqueta la salida validada + el proveedor que la generó.
# Sintaxis: NamedTuple crea una tupla inmutable con campos con nombre.
# Lógica: después de que un LLM responde, necesitamos saber QUÉ modelo produjo
# la respuesta (Gemini u Ollama) para registrar el uso de proveedores.
class Tagged(NamedTuple):
    """Salida validada + el proveedor que realmente la produjo."""

    data: BaseModel      # El objeto Pydantic validado (StoryAnalysis, InvestEvaluation, etc.)
    provider: str        # Nombre del proveedor que lo generó ("gemini" o "ollama")


# _finisher: crea un Runnable que valida la salida del LLM y la empaqueta con Tagged.
# Sintaxis: retorna una RunnableLambda (función envuelta como cadena LangChain).
# Lógica: después de que el LLM devuelve una respuesta, este paso:
# 1) Verifica que no sea None (respuesta vacía).
# 2) Si es un dict, lo convierte al esquema Pydantic correcto.
# 3) Lo empaqueta con el nombre del proveedor en un Tagged.
def _finisher(name: str, schema: type[BaseModel]) -> RunnableLambda:
    def _finish(out: Any) -> Tagged:
        # Si el modelo devolvió None, lanza excepción de parseo
        if out is None:
            raise OutputParserException("El modelo devolvió una respuesta vacía.")
        # Si la salida es un diccionario, la valida contra el esquema Pydantic
        if isinstance(out, dict):
            out = schema.model_validate(out)
        # Empaqueta la salida validada con el nombre del proveedor
        return Tagged(out, name)

    # Envuelve la función _finish como una RunnableLambda de LangChain
    return RunnableLambda(_finish, name=f"tag_{name}")


# build_chain: construye una cadena completa para un nodo del grafo.
# Sintaxis: recibe un prompt, un esquema Pydantic y una lista de proveedores.
# Retorna un solo Runnable con retry + fallback.
# Lógica: por cada proveedor, crea una cadena:
#   prompt | llm.with_structured_output(schema) | _finisher
# Luego le agrega retry (1 reintento si falla el esquema) y fallback
# (si el primer proveedor falla, pasa al siguiente).
def build_chain(
    prompt: ChatPromptTemplate,          # Plantilla del prompt (ej: ANALYSIS_PROMPT)
    schema: type[BaseModel],             # Esquema Pydantic que el LLM debe devolver
    providers: list[tuple[str, BaseChatModel]],  # Lista de proveedores LLM
) -> Runnable:
    """prompt | llm.with_structured_output(schema) por proveedor, encadenados con with_fallbacks.

    - Si la salida no cumple el esquema Pydantic -> 1 reintento en el MISMO proveedor.
    - Si falla igual, o hay error de red / cuota / timeout -> pasa al siguiente proveedor.
    """
    # Si no hay proveedores configurados, no se puede hacer nada
    if not providers:
        raise RuntimeError(
            "No hay proveedores LLM disponibles. Configura GOOGLE_API_KEY o inicia Ollama."
        )

    branches: list[Runnable] = []  # Lista de cadenas (una por proveedor)

    # Por cada proveedor, construye una cadena completa
    for name, llm in providers:
        # Cadena: prompt -> LLM con salida estructurada -> tag con nombre del proveedor
        branch = prompt | llm.with_structured_output(schema) | _finisher(name, schema)

        # Importa errores específicos por proveedor para el retry (lazy import)
        retry_errors = [ValidationError, OutputParserException]
        if name == "gemini":
            try:
                from google.api_core.exceptions import GoogleAPIError
                retry_errors.append(GoogleAPIError)  # Reintenta en errores 503/429 de Gemini
            except ImportError:
                pass  # Si no está instalado, no agrega (fallback seguirá funcionando)

        # Agrega retry: si el LLM falla por esquema inválido o error temporal,
        # reintenta 1 vez más. stop_after_attempt=2 = 1 original + 1 reintento.
        branches.append(
            branch.with_retry(
                retry_if_exception_type=tuple(retry_errors),
                stop_after_attempt=2,              # Máximo 2 intentos total
                wait_exponential_jitter=False,     # Sin espera exponencial
            )
        )

    # Desempaqueta la primera rama y las demás como fallbacks.
    # first.with_fallbacks(rest): si falla first, intenta rest[0], luego rest[1], etc.
    first, *rest = branches
    return first.with_fallbacks(rest) if rest else first  # Si solo hay 1 proveedor, no hay fallback


# build_chains: crea todas las cadenas del validador de una sola vez.
# Sintaxis: retorna un diccionario con una cadena por cada nodo del grafo que usa LLM.
# Lógica: cada nodo del grafo (analizar, invest, ambigüedad, criterios, reescribir)
# tiene su propia cadena con su propio prompt y esquema Pydantic.
def build_chains(providers: list[tuple[str, BaseChatModel]]) -> dict[str, Runnable]:
    return {
        "relevance": build_chain(prompts.RELEVANCE_PROMPT, RelevanceResult, providers),  # Nodo: relevancia
        "analysis": build_chain(prompts.ANALYSIS_PROMPT, StoryAnalysis, providers),     # Nodo: analizar
        "invest": build_chain(prompts.INVEST_PROMPT, InvestEvaluation, providers),       # Nodo: invest
        "ambiguity": build_chain(prompts.AMBIGUITY_PROMPT, AmbiguityReport, providers),  # Nodo: ambigüedad
        "criteria": build_chain(prompts.CRITERIA_PROMPT, AcceptanceCriteria, providers), # Nodo: criterios
        "rewrite": build_chain(prompts.REWRITE_PROMPT, RewriteSuggestion, providers),    # Nodo: reescribir
    }

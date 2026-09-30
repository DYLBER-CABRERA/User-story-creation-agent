"""Proveedores LLM: Ollama local, Gemini API y Groq API (con respaldo automático)."""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from .config import Settings, get_settings


def build_providers(
    settings: Settings | None = None,
    order: tuple[str, ...] | list[str] | None = None,
    modelos: dict[str, str] | None = None,
) -> list[tuple[str, BaseChatModel]]:
    """Construye la lista de proveedores en el orden dado.

    order:   reemplaza settings.provider_order (ej. ("gemini", "ollama") si el
             usuario eligió Gemini como primario; el otro queda de respaldo).
    modelos: sobreescribe el modelo por proveedor (ej. {"gemini": "gemini-2.5-pro"});
             los proveedores no incluidos usan el modelo del .env.
    """
    s = settings or get_settings()
    names = tuple(order) if order is not None else s.provider_order
    modelos = modelos or {}
    providers: list[tuple[str, BaseChatModel]] = []
    for name in names:
        if name == "ollama":
            from langchain_ollama import ChatOllama

            # num_gpu=-1: todas las capas a la GPU (si no cabe, Ollama falla en
            # vez de bajar en silencio a CPU). num_predict solo se envía si es un
            # tope positivo: con -1/0 se omite y Ollama genera sin límite artificial.
            kwargs: dict = {"num_gpu": -1}
            if s.ollama_num_predict > 0:
                kwargs["num_predict"] = s.ollama_num_predict
            providers.append(
                (
                    "ollama",
                    ChatOllama(
                        model=modelos.get("ollama", s.ollama_model),
                        base_url=s.ollama_base_url,
                        temperature=s.temperature,
                        num_ctx=s.ollama_num_ctx,  # ventana prompt+salida
                        **kwargs,
                    ),
                )
            )
        elif name == "gemini":
            if not s.google_api_key:
                continue
            from langchain_google_genai import ChatGoogleGenerativeAI

            providers.append(
                (
                    "gemini",
                    ChatGoogleGenerativeAI(
                        model=modelos.get("gemini", s.gemini_model),
                        google_api_key=s.google_api_key,
                        temperature=s.temperature,
                    ),
                )
            )
        elif name == "groq":
            if not s.groq_api_key:
                continue
            from langchain_groq import ChatGroq

            providers.append(
                (
                    "groq",
                    ChatGroq(
                        model=modelos.get("groq", s.groq_model),
                        api_key=s.groq_api_key,
                        temperature=s.temperature,
                    ),
                )
            )
    return providers

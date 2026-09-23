"""Proveedores optimizados para velocidad: contexto y num_predict acotados en Ollama.

Lógica central:
  build_providers() devuelve una lista ORDENADA de (nombre, cliente LLM).
  El primer elemento es el proveedor principal; el resto son respaldos que
  LangChain usará vía with_fallbacks() si el principal falla.
"""
from __future__ import annotations  # anotaciones perezosas (list[...] moderno)

# BaseChatModel: tipo base de LangChain al que pertenecen ChatOllama y
# ChatGoogleGenerativeAI -> sirve para tipar la lista de retorno.
from langchain_core.language_models.chat_models import BaseChatModel

# Settings y get_settings: config del .env (modelos, URL, temperature, orden)
from .config import Settings, get_settings

# El punto inicial ("from .") importa RELATIVO al paquete generador/:
# .config => generador/config.py


def build_providers(
    settings: Settings | None = None,          # config opcional (si no, se lee del .env)
    order: tuple[str, ...] | list[str] | None = None,  # orden p.ej. ("gemini","ollama")
    modelos: dict[str, str] | None = None,     # override de modelo por proveedor
) -> list[tuple[str, BaseChatModel]]:
    """Construye la lista de proveedores en el orden dado.

    order:   reemplaza settings.provider_order (ej. ("gemini", "ollama") si el
             usuario eligió Gemini como primario; el otro queda de respaldo).
    modelos: sobreescribe el modelo por proveedor (ej. {"gemini": "gemini-2.5-pro"});
             los proveedores no incluidos usan el modelo del .env.
    """
    # `or` cortocircuito: si settings es None, cae a get_settings() (lee .env)
    s = settings or get_settings()
    # order explícito tiene prioridad; si no, el del .env ("ollama,gemini")
    names = tuple(order) if order is not None else s.provider_order
    modelos = modelos or {}  # dict vacío si no se pasó override (evita None)
    providers: list[tuple[str, BaseChatModel]] = []  # acumulador de salida
    for name in names:  # itera en el ORDEN deseado (primario primero)
        if name == "ollama":
            # Import local (deferred): solo carga langchain_ollama si se usa
            # Ollama -> arranque más rápido y sin exigir la librería si no aplica.
            from langchain_ollama import ChatOllama

            providers.append(
                (
                    "ollama",
                    ChatOllama(
                        # modelos.get("ollama", s.ollama_model): si el usuario
                        # pasó un modelo puntual se usa ese; si no, el del .env
                        model=modelos.get("ollama", s.ollama_model),
                        base_url=s.ollama_base_url,  # http://localhost:11434
                        temperature=s.temperature,   # creatividad de la muestra
                        num_ctx=s.ollama_num_ctx,       # menos contexto = arranque más rápido
                        num_predict=s.ollama_num_predict,  # tope de salida = no se dispara la generación
                    ),
                )
            )
        elif name == "gemini":
            if not s.google_api_key:
                # continue -> salta ESTE nombre y sigue con el siguiente de names:
                # sin clave no hay API de Google; no se agrega a la lista (el
                # sistema queda solo con Ollama en vez de fallar después).
                continue
            # Import local igual que arriba, solo si hay clave
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
        # nombres desconocidos en PROVIDER_ORDER se ignoran silenciosamente
    return providers  # [] vacío => quien llame debe tratar "sin proveedores"

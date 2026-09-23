# Docstring del módulo: describe que este archivo construye los modelos de chat
# (Gemini y Ollama) y verifica si están disponibles.
# Sintaxis: triple comilla doble.
# Lógica: centraliza la creación de los proveedores LLM para que otros
# módulos no tengan que importar directamente las librerías de Gemini/Ollama.
"""Construcción de los modelos de chat (Gemini + Ollama) y chequeo de salud."""
from __future__ import annotations  # Anotaciones de tipo diferidas (PEP 563)

import urllib.request  # Módulo estándar para hacer peticiones HTTP simples

from langchain_core.language_models.chat_models import BaseChatModel  # Clase base abstracta de LangChain para modelos de chat

from .config import Settings, get_settings  # Importa la configuración del módulo hermano config.py


# build_providers: crea la lista de proveedores LLM ordenados por preferencia.
# Sintaxis: función con retorno tipado -> list[tuple[str, BaseChatModel]].
# Lógica: recorre provider_order (ej: ["gemini", "ollama"]) y crea el objeto
# de chat correspondiente por cada uno. Si Gemini no tiene API key, se salta
# y el sistema arranca solo con Ollama. Devuelve tuplas (nombre, modelo).
def build_providers(settings: Settings | None = None) -> list[tuple[str, BaseChatModel]]:
    """Devuelve [(nombre, modelo)] en el orden de PROVIDER_ORDER.

    Gemini se omite si no hay GOOGLE_API_KEY; así el sistema arranca solo con Ollama.
    """
    # Si no se pasan settings, usa los valores por defecto del .env
    s = settings or get_settings()

    # Lista vacía que se irá llenando con tuplas (nombre, modelo_llm)
    providers: list[tuple[str, BaseChatModel]] = []

    # Itera sobre el orden de proveedores configurado (ej: ["gemini", "ollama"])
    for name in s.provider_order:
        # Si el proveedor es "gemini"...
        if name == "gemini":
            # ...pero no hay API key configurada, lo salta (continue al siguiente)
            if not s.google_api_key:
                continue
            # Importación lazy: solo importa la librería de Google si se va a usar.
            # Así, si solo usas Ollama, no necesitas instalar langchain-google-genai.
            from langchain_google_genai import ChatGoogleGenerativeAI

            # Crea el cliente de Gemini con los parámetros de configuración
            providers.append(
                (
                    "gemini",  # Nombre identificador del proveedor
                    ChatGoogleGenerativeAI(
                        model=s.gemini_model,         # Ej: "gemini-2.5-flash"
                        google_api_key=s.google_api_key,  # La API key de Google
                        temperature=s.temperature,    # 0 = determinista
                        timeout=s.timeout_s,          # Segundos máximos de espera
                        max_retries=1,                # 1 reintento automático
                    ),
                )
            )
        # Si el proveedor es "ollama"...
        elif name == "ollama":
            # Importación lazy de la librería de Ollama
            from langchain_ollama import ChatOllama

            # Crea el cliente de Ollama (corre en localhost:11434 por defecto)
            # Sin timeout: Ollama corre local y puede tardar en responder,
            # especialmente con modelos grandes o si es la primera llamada.
            providers.append(
                (
                    "ollama",  # Nombre identificador del proveedor
                    ChatOllama(
                        model=s.ollama_model,          # Ej: "qwen2.5:3b"
                        base_url=s.ollama_base_url,    # Ej: "http://localhost:11434"
                        temperature=s.temperature,     # 0 = determinista
                    ),
                )
            )
    return providers  # Lista de tuplas: [("gemini", modelo_gemini), ("ollama", modelo_ollama)]


# check_health: verifica el estado de cada proveedor LLM.
# Sintaxis: función que retorna un diccionario con la salud de cada proveedor.
# Lógica: para cada proveedor, verifica si está disponible. Para Gemini, solo
# checa si hay API key. Para Ollama, hace una petición HTTP real al servidor
# para ver si está corriendo y si tiene el modelo instalado.
def check_health(settings: Settings | None = None) -> dict[str, dict]:
    """Estado de cada proveedor para mostrarlo en la interfaz."""
    s = settings or get_settings()

    # Estado de Gemini: solo depende de si hay API key configurada
    status: dict[str, dict] = {
        "gemini": {
            "ok": bool(s.google_api_key),  # True si la key no es cadena vacía
            "detalle": s.gemini_model if s.google_api_key else "Falta GOOGLE_API_KEY",
        }
    }

    try:
        # Petición HTTP a la API de tags de Ollama para listar modelos instalados.
        # urllib.request.urlopen abre una conexión con timeout de 2 segundos.
        with urllib.request.urlopen(f"{s.ollama_base_url}/api/tags", timeout=2) as resp:
            import json  # Importa json solo aquí (lazy) para parsear la respuesta

            # Extrae los nombres de todos los modelos instalados en Ollama
            models = [m["name"] for m in json.loads(resp.read()).get("models", [])]

        # Verifica si el modelo configurado (ej: "llama3.1:8b") está entre los instalados.
        # Compara exacto o por prefijo (ej: "llama3.1" matchea "llama3.1:8b").
        tiene = any(m == s.ollama_model or m.startswith(s.ollama_model.split(":")[0]) for m in models)

        status["ollama"] = {
            "ok": tiene,
            "detalle": s.ollama_model if tiene else f"Ollama activo pero sin '{s.ollama_model}' (ollama pull {s.ollama_model})",
        }
    except Exception:
        # Si Ollama no responde (no está corriendo, puerto cerrado, etc.)
        status["ollama"] = {"ok": False, "detalle": "Ollama no responde (¿ejecutaste 'ollama serve'?)"}

    return status  # Dict con estado de cada proveedor: {"gemini": {"ok": True, ...}, "ollama": {...}}

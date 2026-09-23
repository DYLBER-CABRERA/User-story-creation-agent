"""Carga de configuración desde variables de entorno (.env).

Lógica general: Python 3.12, sin dependencias externas salvo python-dotenv.
"""

# from __future__ import annotations -> anota que las anotaciones de tipo sean
# strings evaluados de forma perezosa (permite list[str] en 3.8+ y adelanta costos)
from __future__ import annotations

# os: módulo estándar para leer variables de entorno (os.getenv)
import os
# dataclass: decorator de stdlib que convierte una clase en un contenedor de datos
# inmutable si se marca con frozen=True (no se puede reasignar atributos)
from dataclasses import dataclass

# load_dotenv: lee el archivo .env y volca sus pares clave=valor a os.environ
# (no pisa variables ya existentes en el entorno del sistema)
from dotenv import load_dotenv

# Carga el .env en el momento de importar este módulo (side effect al importar).
# Si .env no existe, no falla: simplemente no agrega nada.
load_dotenv()


# frozen=True -> instancia inmutable: Settings no se puede modificar tras crearse,
# lo que evita que una parte del código cambie la config a mitad de ejecución.
@dataclass(frozen=True)
class Settings:
    """Contrato de configuración: todos los campos son de valor primitivo."""
    ollama_model: str           # nombre del modelo local, ej. "llama3.1:8b"
    ollama_base_url: str        # URL del servidor Ollama, ej. "http://localhost:11434"
    ollama_num_ctx: int         # tamaño de ventana de contexto (tokens) que reserva Ollama
    ollama_num_predict: int     # tope máximo de tokens que generará el modelo (salida)
    google_api_key: str         # clave de Google para Gemini; "" si no está configurada
    gemini_model: str           # nombre del modelo Gemini, ej. "gemini-2.5-flash"
    provider_order: tuple[str, ...]  # orden de proveedores p.ej. ("ollama", "gemini")
    temperature: float          # aleatoriedad del modelo (0 = determinista, 1 = creativo)


def get_settings() -> Settings:
    """Construye Settings leyendo cada variable del entorno, con valores por defecto.

    os.getenv("CLAVE", defecto):
      - si la variable existe (y no está vacía para str), devuelve su valor;
      - si no, devuelve el segundo argumento (el defecto).
    int(...) y float(...) convierten el string del entorno a número;
    si el string no es numérico lanza ValueError (falla temprano y explícito).
    """
    return Settings(
        # Modelo local por defecto si .env no define OLLAMA_MODEL
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        # URL por defecto: Ollama corre en el puerto 11434 en localhost
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        # Contexto acotado a 4096 tokens: arranca más rápido y no "suda" memoria
        ollama_num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "4096")),
        # Generación acotada a 1800 tokens: evita que el modelo se alargue de más
        ollama_num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "1800")),
        # .strip() quita espacios accidentales; "" significa "sin clave" -> sin Gemini
        google_api_key=os.getenv("GOOGLE_API_KEY", "").strip(),
        # Modelo Gemini por defecto si .env no define GEMINI_MODEL
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        # PROVIDER_ORDER es una lista separada por comas, ej. "ollama,gemini".
        # split(",") parte la cadena; la comprensión limpia espacios, pasa a minúsculas
        # y descarta tokens vacíos (evita ("",) si hay comas dobles o espacios).
        provider_order=tuple(
            p.strip().lower() for p in os.getenv("PROVIDER_ORDER", "ollama,gemini").split(",") if p.strip()
        ),
        # Temperatura por defecto 0.4: algo de variedad sin perder coherencia
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.4")),
    )

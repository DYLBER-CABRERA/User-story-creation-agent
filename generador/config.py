from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    ollama_model: str
    ollama_base_url: str
    ollama_num_ctx: int
    ollama_num_predict: int
    google_api_key: str
    gemini_model: str
    gemini_max_output_tokens: int
    groq_api_key: str
    groq_model: str
    provider_order: tuple[str, ...]
    temperature: float


def get_settings() -> Settings:
    return Settings(
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "8192")),
        # -1 = sin tope de generación (el modelo para al cerrar su JSON)
        ollama_num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "-1")),
        google_api_key=os.getenv("GOOGLE_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        # tope de SALIDA de Gemini (tokens que puede escribir en la respuesta).
        # 0 = no enviarlo y dejar el default del modelo (~8192, insuficiente para
        # ~30 historias). Subirlo (p. ej. 32768) evita respuestas truncadas.
        gemini_max_output_tokens=int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "0")),
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        groq_model=os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
        provider_order=tuple(
            p.strip().lower()
            for p in os.getenv("PROVIDER_ORDER", "ollama,gemini,groq").split(",")
            if p.strip()
        ),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.4")),
    )

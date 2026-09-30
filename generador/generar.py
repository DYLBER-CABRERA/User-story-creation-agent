"""Generador de historias de usuario: UNA sola llamada al LLM para las 3 listas.

Pensado para modelos locales de Ollama:
- method="json_schema" -> usa el `format` nativo de Ollama (más rápido que tool-calling).
- Sin tope de salida (num_predict=-1) -> el modelo escribe todas las historias pedidas,
  aunque tarde minutos.
- Un solo prompt para las N historias -> evita el costo fijo de N llamadas separadas.
- Un tema obligatorio y distinto por historia (temas.py) -> el modelo no puede rellenar
  la cantidad pedida repitiendo la misma idea, y se queda dentro del alcance del proyecto.
- Validación de cantidades -> si el modelo devuelve menos historias de las pedidas,
  se reintenta; si persiste, error explícito (nunca se entregan listas cortas en silencio).
- with_retry -> si Pydantic detecta historias repetidas o mal formadas, reintenta antes
  de rendirse; with_fallbacks -> si Ollama no responde, pasa a Gemini (si hay clave).
"""
from __future__ import annotations

import sys
import time

from langchain_core.exceptions import OutputParserException
from langchain_core.runnables import Runnable
from pydantic import ValidationError

from .config import Settings, get_settings
from .llm import build_providers
from .prompts import GENERATE_PROMPT
from .schemas import HistoriasGeneradas
from .temas import formatear, temas_para

APP_NAME_DEFAULT = "BusetasApp Manizales"
CONTEXT_DEFAULT = (
    "BusetasApp es una aplicación para consultar las rutas de las busetas de Manizales: "
    "catálogo de rutas con recorrido en mapa y paradas, horarios y días de operación "
    "(lunes a viernes, sábados, domingos y festivos), ubicación de las busetas en tiempo "
    "real con tiempo estimado de llegada (ETA) a una parada, planificación de viaje con "
    "origen y destino, y búsqueda por número o nombre de ruta, barrio o punto de interés. "
    "Incluye un módulo administrativo (crear y actualizar rutas, horarios, paradas y "
    "busetas, publicar avisos generales y ver estadísticas básicas) y un módulo de "
    "conductores (reportar la posición de la buseta durante el recorrido). El pasajero "
    "puede consultar sin cuenta; guardar favoritas y recibir notificaciones requiere "
    "usuario registrado. Fuera de alcance: pagos, tarjetas de recarga y transporte fuera "
    "de Manizales. Roles: pasajero, conductor, administrador."
)


def build_chain(providers: list[tuple[str, object]] | None = None) -> Runnable:
    provs = providers if providers is not None else build_providers()
    if not provs:
        raise RuntimeError("No hay proveedores LLM disponibles. Configura Ollama o GOOGLE_API_KEY.")
    branches = []
    for _, llm in provs:
        branch = GENERATE_PROMPT | llm.with_structured_output(HistoriasGeneradas)
        branches.append(
            branch.with_retry(
                retry_if_exception_type=(ValidationError, OutputParserException),
                stop_after_attempt=2,
                wait_exponential_jitter=False,
            )
        )
    first, *rest = branches
    return first.with_fallbacks(rest) if rest else first


def _problema_conteos(
    out: HistoriasGeneradas, n_pasajero: int, n_conductor: int, n_admin: int
) -> str | None:
    """None si los conteos cuadran; si no, detalle de lo que faltó/ sobró."""
    faltan = []
    for rol, lista, esperado in (
        ("pasajero", out.pasajero, n_pasajero),
        ("conductor", out.conductor, n_conductor),
        ("administrador", out.administrador, n_admin),
    ):
        if len(lista) != esperado:
            faltan.append(f"{rol}: {len(lista)}/{esperado}")
    return ", ".join(faltan) if faltan else None


MAX_INTENTOS = 2  # igual que with_retry: dos pasadas del modelo por respuestas incompletas


def generar_historias(
    n_pasajero: int = 6,
    n_conductor: int = 5,
    n_admin: int = 4,
    app_name: str = APP_NAME_DEFAULT,
    context: str | None = None,
    settings: Settings | None = None,
    chain: Runnable | None = None,
    order: tuple[str, ...] | list[str] | None = None,
    modelos: dict[str, str] | None = None,
    debug: bool = False,
) -> tuple[HistoriasGeneradas, float]:
    s = settings or get_settings()
    if context is None:
        # Contexto completo desde el documento de alcance (fuente única de verdad);
        # CONTEXT_DEFAULT solo como respaldo si el documento no existe.
        from .specs import contexto_proyecto
        context = contexto_proyecto() or CONTEXT_DEFAULT
    chain = chain or build_chain(build_providers(s, order=order, modelos=modelos))
    payload = {
        "app_name": app_name,
        "context": context,
        "n_pasajero": n_pasajero,
        "n_conductor": n_conductor,
        "n_admin": n_admin,
        "temas_pasajero": formatear(temas_para("pasajero", n_pasajero)),
        "temas_conductor": formatear(temas_para("conductor", n_conductor)),
        "temas_administrador": formatear(temas_para("administrador", n_admin)),
    }
    if debug:
        mensajes = GENERATE_PROMPT.format_messages(**payload)
        total = sum(len(m.content) for m in mensajes)
        print(
            f"===== PROMPT EXACTO — {len(mensajes)} mensaje(s), {total} caracteres =====",
            file=sys.stderr,
        )
        for msg in mensajes:
            print(f"\n----- {msg.type} ({len(msg.content)} caracteres) -----",
                  file=sys.stderr)
            print(msg.content, file=sys.stderr)
        print("\n===== FIN PROMPT =====", file=sys.stderr)
    t0 = time.perf_counter()
    out: HistoriasGeneradas | None = None
    problema: str | None = None
    for intento in range(1, MAX_INTENTOS + 1):
        t1 = time.perf_counter()
        out = chain.invoke(payload)
        if isinstance(out, dict):
            out = HistoriasGeneradas.model_validate(out)
        # Exigimos las cantidades pedidas: si el modelo vino corto, se reintenta
        # (los modelos locales a veces "se rinden" a mitad del JSON).
        problema = _problema_conteos(out, n_pasajero, n_conductor, n_admin)
        if debug:
            dt = time.perf_counter() - t1
            estado = "conteos ok" if problema is None else f"reintento por conteos ({problema})"
            print(f"[intento {intento}] respuesta del modelo en {dt:.1f} s — {estado}",
                  file=sys.stderr)
        if problema is None:
            break
    else:
        raise RuntimeError(
            f"El modelo no generó todas las historias pedidas ({problema}). "
            "Se intentó 2 veces. Prueba con un modelo mayor (ej. qwen2.5:3b) "
            "o reduce las cantidades."
        )
    elapsed = time.perf_counter() - t0
    return out, elapsed

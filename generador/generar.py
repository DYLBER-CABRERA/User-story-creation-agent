"""Generador de historias de usuario: UNA sola llamada al LLM para las 4 listas.

Pensado para modelos locales de Ollama:
- method="json_schema" -> usa el `format` nativo de Ollama (mas rapido que tool-calling).
- Sin tope de salida (num_predict=-1) -> el modelo escribe todas las historias pedidas,
  aunque tarde minutos.
- Un solo prompt para las N historias -> evita el costo fijo de N llamadas separadas.
- Un tema obligatorio y distinto por historia (temas.py) -> el modelo no puede rellenar
  la cantidad pedida repitiendo la misma idea, y se queda dentro del alcance del proyecto.
- El numero de historias por rol se deriva automaticamente de la cantidad de temas
  definidos en temas.py, sin que el usuario tenga que indicarlo.
- Validacion de cantidades -> si el modelo devuelve menos historias de las esperadas,
  se reintenta; si persiste, error explicito (nunca se entregan listas cortas en silencio).
- with_retry -> si Pydantic detecta historias repetidas o mal formadas, reintenta antes
  de rendirse; with_fallbacks -> si el principal no responde, pasa al siguiente
  (Gemini o Groq, si hay clave).

Roles (4): Pasajero, Jefe de Operaciones, Secretaria de Movilidad, Administrador.
El rol Conductor fue eliminado del alcance (contexto-busetasapp.md s4).
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
    "BusetasApp es una aplicacion para consultar las rutas de las busetas de Manizales, "
    "operadas por empresas como Socobuses, Sideral y Serviturismo: catalogo de rutas con "
    "recorrido en mapa y paradas, horarios y dias de operacion (lunes a viernes, sabados, "
    "domingos y festivos), frecuencias variables por franja horaria, ubicacion de las "
    "busetas con tiempo estimado de llegada (ETA) a una parada, planificacion de viaje con "
    "origen y destino, y busqueda por numero o nombre de ruta, barrio o punto de interes "
    "(los usuarios se orientan por hitos como la Catedral, El Cable, la Carrera 23 o "
    "Fundadores). Hay cuatro roles. Pasajero: consulta sin cuenta; guardar favoritas y "
    "recibir notificaciones requiere usuario registrado. Jefe de operaciones: responsable "
    "operativo de una empresa; asigna conductores a rutas ya registradas, define el "
    "rodamiento del dia, publica avisos generales y consulta estadisticas basicas. "
    "Secretaria de Movilidad: alimenta la base de datos; impone rutas a cada empresa, "
    "gestiona paraderos y registra cambios de movilidad en la ciudad. Administrador: "
    "dueno de la plataforma, con control total (usuarios, roles, empresas y configuracion). "
    "Los conductores NO son usuarios de la plataforma; solo existen como datos del "
    "rodamiento. Fuera de alcance: pagos, tarjetas de recarga, transporte fuera de "
    "Manizales y modulo de conductor."
)


def build_chain(
    providers: list[tuple[str, object]] | None = None,
    sin_fallbacks: bool = False,
) -> Runnable:
    provs = providers if providers is not None else build_providers()
    if not provs:
        raise RuntimeError(
            "No hay proveedores LLM disponibles. Configura Ollama, GOOGLE_API_KEY o GROQ_API_KEY."
        )
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
    if sin_fallbacks:
        return branches[0]
    first, *rest = branches
    return first.with_fallbacks(rest) if rest else first


def _problema_conteos(
    out: HistoriasGeneradas,
    n_pasajero: int,
    n_jefe: int,
    n_secretaria: int,
    n_admin: int,
) -> str | None:
    """None si los conteos cuadran; si no, detalle de lo que falto/sobro."""
    faltan = []
    for rol, lista, esperado in (
        ("pasajero", out.pasajero, n_pasajero),
        ("jefe_operaciones", out.jefe_operaciones, n_jefe),
        ("secretaria_movilidad", out.secretaria_movilidad, n_secretaria),
        ("administrador", out.administrador, n_admin),
    ):
        if len(lista) != esperado:
            faltan.append(f"{rol}: {len(lista)}/{esperado}")
    return ", ".join(faltan) if faltan else None


MAX_INTENTOS = 2  # igual que with_retry: dos pasadas del modelo por respuestas incompletas


def _operaciones_rnf() -> str:
    """Lista 'N. Nombre - operacion' de las funcionalidades, para que el
    modelo proponga un RNF por cada una en rnf_especs."""
    from .specs import CATALOGO, RNF_OPERACION
    return "\n".join(f"  {f.num}. {f.nombre} - {RNF_OPERACION[f.num]}" for f in CATALOGO)


def generar_historias(
    app_name: str = APP_NAME_DEFAULT,
    context: str | None = None,
    settings: Settings | None = None,
    chain: Runnable | None = None,
    order: tuple[str, ...] | list[str] | None = None,
    modelos: dict[str, str] | None = None,
    debug: bool = False,
) -> tuple[HistoriasGeneradas, float]:
    """Genera las historias de usuario para los 4 roles del proyecto.

    La cantidad de historias por rol se deriva automaticamente de los temas
    definidos en temas.py: una historia por cada funcionalidad del alcance.
    """
    s = settings or get_settings()
    if context is None:
        from .specs import contexto_proyecto
        context = contexto_proyecto() or CONTEXT_DEFAULT
    chain = chain or build_chain(build_providers(s, order=order, modelos=modelos))

    temas_p = temas_para("pasajero")
    temas_j = temas_para("jefe_operaciones")
    temas_sm = temas_para("secretaria_movilidad")
    temas_a = temas_para("administrador")
    n_pasajero = len(temas_p)
    n_jefe = len(temas_j)
    n_secretaria = len(temas_sm)
    n_admin = len(temas_a)

    payload = {
        "app_name": app_name,
        "context": context,
        "n_pasajero": n_pasajero,
        "n_jefe": n_jefe,
        "n_secretaria": n_secretaria,
        "n_admin": n_admin,
        "temas_pasajero": formatear(temas_p),
        "temas_jefe_operaciones": formatear(temas_j),
        "temas_secretaria_movilidad": formatear(temas_sm),
        "temas_administrador": formatear(temas_a),
        "operaciones_rnf": _operaciones_rnf(),
    }
    if debug:
        mensajes = GENERATE_PROMPT.format_messages(**payload)
        total = sum(len(m.content) for m in mensajes)
        print(
            f"===== PROMPT EXACTO - {len(mensajes)} mensaje(s), {total} caracteres =====",
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
        problema = _problema_conteos(out, n_pasajero, n_jefe, n_secretaria, n_admin)
        if debug:
            dt = time.perf_counter() - t1
            estado = "conteos ok" if problema is None else f"reintento por conteos ({problema})"
            print(f"[intento {intento}] respuesta del modelo en {dt:.1f} s - {estado}",
                  file=sys.stderr)
        if problema is None:
            break
    else:
        raise RuntimeError(
            f"El modelo no genero todas las historias pedidas ({problema}). "
            "Se intento 2 veces. Prueba con un modelo mayor (ej. qwen2.5:3b) "
            "o reduce los temas en temas.py."
        )
    elapsed = time.perf_counter() - t0
    if out.rnf_especs:
        from .specs import guardar_propuestas_rnf
        guardadas = guardar_propuestas_rnf(out.rnf_especs)
        if debug:
            print(f"[rnf] {guardadas} cifras RNF propuestas guardadas en control.json",
                  file=sys.stderr)
    return out, elapsed

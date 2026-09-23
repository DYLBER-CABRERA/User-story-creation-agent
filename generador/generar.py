"""Generador de historias de usuario: UNA sola llamada al LLM para las 3 listas.

Lógica general del módulo (dos funciones públicas):

  build_chain()      -> ensambla la cadena LCEL:
        GENERATE_PROMPT | llm.with_structured_output(HistoriasGeneradas)
        .with_retry(...)      reintenta si Pydantic rechaza la salida
        .with_fallbacks(...)  pasa al siguiente proveedor si el principal truena

  generar_historias() -> rellena el prompt (cantidades + temas) y ejecuta la
        única chain.invoke(...); devuelve (HistoriasGeneradas, segundos).

Pensado para modelos locales de Ollama:
- method="json_schema" -> usa el `format` nativo de Ollama (más rápido que tool-calling).
- num_ctx / num_predict acotados -> el modelo no procesa ni genera de más.
- Un solo prompt para las 15 historias -> evita el costo fijo de 15 llamadas separadas.
- Un tema obligatorio y distinto por historia (temas.py) -> el modelo no puede rellenar
  la cantidad pedida repitiendo la misma idea, y se queda dentro del alcance del proyecto.
- with_retry -> si Pydantic detecta historias repetidas o mal formadas, reintenta antes
  de rendirse; with_fallbacks -> si Ollama no responde, pasa a Gemini (si hay clave).
"""
from __future__ import annotations  # anotaciones de tipo perezosas

# time.perf_counter(): reloj de alta resolución (monótono) ideal para medir
# duraciones; se usa para cronometrar la invocación al LLM.
import time

# OutputParserException: error de LangChain cuando el LLM devuelve texto que
# no se pudo parsear al esquema pedido -> también debe disparar el retry.
from langchain_core.exceptions import OutputParserException
# Runnable: tipo base de todo componente componible con | en LCEL
# (prompt, modelo, retry, fallback son todos Runnables).
from langchain_core.runnables import Runnable
# ValidationError: error de Pydantic cuando un modelo no pasa sus validadores
# (incluye nuestros model_validator de duplicados).
from pydantic import ValidationError

# Imports internos del paquete (punto relativo = mismo paquete generador/)
from .config import Settings, get_settings     # Settings del .env
from .llm import build_providers               # lista [(nombre, cliente LLM)]
from .prompts import GENERATE_PROMPT           # plantilla system+human
from .schemas import HistoriasGeneradas        # esquema Pydantic de salida
from .temas import formatear, temas_para       # temas obligatorios por rol

# Valores por defecto de la app (si CLI/UI no los pisan)
APP_NAME_DEFAULT = "BusetasApp Manizales"
# Contexto por defecto: el LLM solo puede generar funcionalidades de aquí adentro
CONTEXT_DEFAULT = (
    "Aplicación para que los pasajeros conozcan las rutas, horarios y días de operación "
    "de las busetas de Manizales, y vean su ubicación en tiempo real por GPS con el tiempo "
    "estimado de llegada. Roles: pasajero, conductor, administrador."
)


def build_chain(providers: list[tuple[str, object]] | None = None) -> Runnable:
    """Construye la cadena LCEL completa (prompt → structured output → retry → fallback).

    providers: lista opcional [(nombre, llm)]; si es None se construye desde .env.
    Retorna un único Runnable listo para .invoke({...}).

    Cadena de decoradores (de adentro hacia afuera):
      1. GENERATE_PROMPT | llm.with_structured_output(schema)
         - |  es el operador LCEL de composición: la salida del prompt (messages)
           entra como entrada del modelo estructurado.
         - with_structured_output(HistoriasGeneradas) hace que el modelo devuelva
           un dict que Pydantic convierte en HistoriasGeneradas (aquí se pueden
           lanzar ValidationError por duplicados).
      2. .with_retry(...) -> reintenta la RAMA si lanza ValidationError u
         OutputParserException; stop_after_attempt=2 => 1 reintento máximo;
         wait_exponential_jitter=False => reintento inmediato (sin espera).
      3. first.with_fallbacks(rest) -> si la rama primaria falla AGOTA sus
         reintentos, LangChain invoca la siguiente rama (otro proveedor).
    """
    # Si no pasaron proveedores, arma la lista desde .env/orden por defecto
    provs = providers if providers is not None else build_providers()
    if not provs:
        # RuntimeError: falla explícita si no hay ni Ollama ni Gemini configurado
        # (mejor que una lista vacía que fallaría después con IndexError)
        raise RuntimeError("No hay proveedores LLM disponibles. Configura Ollama o GOOGLE_API_KEY.")
    branches = []  # una "rama" por proveedor, cada una con su propio retry
    for _, llm in provs:  # desempaqueta (nombre, llm); el nombre solo se usa fuera
        # Composición prompt → modelo estructurado (1 sola rama base)
        branch = GENERATE_PROMPT | llm.with_structured_output(HistoriasGeneradas)
        branches.append(
            # retry_if_exception_type: tupla de tipos que SÍ disparan reintento.
            branch.with_retry(
                retry_if_exception_type=(ValidationError, OutputParserException),
                stop_after_attempt=2,            # 1 intento + 1 reintento
                wait_exponential_jitter=False,   # sin backoff exponencial
            )
        )
    # PEP 448 / extended unpacking: first = branches[0], rest = branches[1:]
    first, *rest = branches
    # Si hay respaldo(s), encadena fallbacks; si solo hay uno, devuelve la rama simple
    return first.with_fallbacks(rest) if rest else first


def generar_historias(
    n_pasajero: int = 6,              # cantidad pedida de historias de pasajero
    n_conductor: int = 5,             # cantidad pedida de conductor
    n_admin: int = 4,                 # cantidad pedida de administrador
    app_name: str = APP_NAME_DEFAULT,  # {app_name} del prompt
    context: str = CONTEXT_DEFAULT,    # {context} del prompt (alcance del proyecto)
    settings: Settings | None = None,  # config opcional (si no, la del .env)
    chain: Runnable | None = None,     # cadena ya armada (la inyectan tests/UI)
    order: tuple[str, ...] | list[str] | None = None,  # orden de proveedores
    modelos: dict[str, str] | None = None,             # override de modelos
) -> tuple[HistoriasGeneradas, float]:
    """Ejecuta LA única llamada al LLM y devuelve (resultado validado, segundos).

    Flujo:
      1. resolver settings (del .env si no se pasó)
      2. resolver chain (build_chain si no se inyectó una)
      3. t0 = reloj; chain.invoke(dict de variables del prompt); t1 = reloj
      4. si la salida vino como dict (algunos proveedores), re-validar con Pydantic
      5. devolver (HistoriasGeneradas, elapsed segundos como float)
    """
    # `or` cortocircuito: si settings es None, lee .env
    s = settings or get_settings()
    # Si no inyectaron cadena, la arma ahora con el orden/modelos pedidos
    chain = chain or build_chain(build_providers(s, order=order, modelos=modelos))
    t0 = time.perf_counter()  # marca de inicio (segundos como float)
    # invoke() -> ejecuta la cadena completa UNA vez con las variables del prompt.
    out = chain.invoke(
        {
            "app_name": app_name,      # se inyecta en {app_name} del SYSTEM
            "context": context,        # se inyecta en {context}
            "n_pasajero": n_pasajero,  # se inyecta en {n_pasajero:02d} (IDs HU-P01..)
            "n_conductor": n_conductor,
            "n_admin": n_admin,
            # temas_para() devuelve N temas (con variantes si N > catálogo);
            # formatear() los numera "1. ...\n2. ..." listos para el prompt
            "temas_pasajero": formatear(temas_para("pasajero", n_pasajero)),
            "temas_conductor": formatear(temas_para("conductor", n_conductor)),
            "temas_administrador": formatear(temas_para("administrador", n_admin)),
        }
    )
    elapsed = time.perf_counter() - t0  # duración total en segundos (float)
    if isinstance(out, dict):
        # Algunos Runnables devuelven dict crudo; re-validar garantiza que los
        # validadores de Pydantic (duplicados) corran igual que en el path normal.
        out = HistoriasGeneradas.model_validate(out)
    # Tupla inmutable: (resultado, duración) — la duración es solo informativa
    return out, elapsed

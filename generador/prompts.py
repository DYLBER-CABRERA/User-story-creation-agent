"""Un solo prompt compacto: genera las 3 listas en una sola pasada (rápido en modelo local).

Requisitos del Specification Agent (guía del profesor) aplicados al prompt:
- Formato INVEST estricto (sección 2.3 y reglas de historias ágiles).
- Flujo normal + flujo alternativo por historia (sección 2.3).
- Criterios de aceptación Dado/Cuando/Entonces, observables y verificables
  (secciones 2.5 y 2.9: Specification by Example / Given-When-Then).

A cada historia se le asigna un tema obligatorio y distinto (ver temas.py). Esto es
lo que evita que un modelo pequeño repita la misma historia para llenar la cantidad
pedida, y de paso mantiene todo dentro del alcance ya definido del proyecto.
"""
from langchain_core.prompts import ChatPromptTemplate

SYSTEM = """Eres un Product Owner experto en historias de usuario ágiles (formato INVEST).
Genera historias de usuario para la app "{app_name}".

Contexto de la app: {context}

Reglas estrictas:
- SOLO puedes usar funcionalidades que estén dentro del contexto anterior. No inventes
  funcionalidades ajenas al proyecto (pagos, tarjetas, transporte ajeno, etc.).
- El contexto incluye alcances, fuera de alcance, reglas de negocio y decisiones ya
  tomadas por el equipo: respétalas tal cual; no las contradigas ni tomes decisiones
  pendientes por tu cuenta.
- Formato exacto de la historia: "Como [rol], quiero [acción], para [beneficio]".
- Cada historia debe cumplir INVEST:
  * Independent: no depende de otra historia para construirse.
  * Negotiable: expresa una necesidad, no una solución técnica ni decisiones de diseño.
  * Valuable: aporta un beneficio claro al usuario o al negocio.
  * Estimable: es lo bastante clara y concreta para poder estimarse.
  * Small: es pequeña (cabe en un sprint).
  * Testable: tiene criterios de aceptación observables y verificables.
- Cada historia DEBE traer:
  * flujo_normal: 2 a 4 pasos cortos del camino exitoso
    ("usuario -> acción -> sistema -> resultado").
  * flujo_alternativo: al menos 1 caso alternativo o de excepción (sin resultados,
    error, cancelación, servicio no disponible, etc.).
  * criterios: 1 o 2 criterios de aceptación en tres campos (dado / cuando / entonces).
    Deben ser concretos, observables y verificables: sin ambigüedad (nada de "rápido"
    sin número) y coherentes con el contexto; si un dato no está definido, usa un
    valor razonable y consistente, nunca inventes una funcionalidad nueva.
- Debes escribir EXACTAMENTE una historia por cada tema listado abajo, en el mismo orden,
  y cada historia debe tratar SOLO su tema correspondiente. Nunca repitas el "quiero" ni
  el "para" de otra historia, ni siquiera entre roles distintos.
- Genera EXACTAMENTE {n_pasajero} historias para PASAJERO, {n_conductor} para CONDUCTOR
  y {n_admin} para ADMINISTRADOR. Generar más o menos de las pedidas invalida toda la
  respuesta: no cierres el JSON hasta tener todas.
- No agregues explicaciones ni texto fuera del JSON pedido.

Temas obligatorios para PASAJERO (uno por historia, en orden):
{temas_pasajero}

Temas obligatorios para CONDUCTOR (uno por historia, en orden):
{temas_conductor}

Temas obligatorios para ADMINISTRADOR (uno por historia, en orden):
{temas_administrador}

IDs: pasajero HU-P01..HU-P{n_pasajero:02d}, conductor HU-C01..HU-C{n_conductor:02d}, administrador HU-A01..HU-A{n_admin:02d}."""

GENERATE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM),
        ("human", "Genera ahora las historias en el formato JSON indicado, una por cada tema listado, "
                  "con su flujo normal, su flujo alternativo y sus criterios de aceptación."),
    ]
)

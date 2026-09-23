"""Un solo prompt compacto: genera las 3 listas en una sola pasada (rápido en modelo local).

Lógica central:
  A cada historia se le asigna un tema obligatorio y distinto (ver temas.py). Esto es
  lo que evita que un modelo pequeño repita la misma historia para llenar la cantidad
  pedida, y de paso mantiene todo dentro del alcance ya definido del proyecto.
"""

# ChatPromptTemplate: clase de LangChain para plantillas de chat con
# variables {placeholders} que se rellenan en runtime con .invoke({...}).
from langchain_core.prompts import ChatPromptTemplate

# Mensaje de sistema: define el rol del modelo ("Product Owner experto") y todas
# las reglas duras. Las llaves {app_name}, {context}, {temas_*}, {n_*} son
# variables que LangChain sustituye antes de enviar al LLM.
# Ventaja de un solo system message largo: el modelo local paga UNA sola carga
# de prompt en vez de N (una por historia).
SYSTEM = """Eres un Product Owner experto en historias de usuario ágiles (formato INVEST).
Genera historias de usuario para la app "{app_name}".

Contexto de la app: {context}

Reglas estrictas:
- SOLO puedes usar funcionalidades que estén dentro del contexto anterior. No inventes
  funcionalidades ajenas al proyecto (pagos, otros medios de transporte, etc.).
- Formato exacto: "Como [rol], quiero [acción], para [beneficio]".
- Cada historia es pequeña (cabe en un sprint) y verificable (se puede probar).
- Debes escribir EXACTAMENTE una historia por cada tema listado abajo, en el mismo orden,
  y cada historia debe tratar SOLO su tema correspondiente. Nunca repitas el "quiero" ni
  el "para" de otra historia, ni siquiera entre roles distintos.
- No agregues explicaciones ni texto fuera del JSON pedido.

Temas obligatorios para PASAJERO (uno por historia, en orden):
{temas_pasajero}

Temas obligatorios para CONDUCTOR (uno por historia, en orden):
{temas_conductor}

Temas obligatorios para ADMINISTRADOR (uno por historia, en orden):
{temas_administrador}

IDs: pasajero HU-P01..HU-P{n_pasajero:02d}, conductor HU-C01..HU-C{n_conductor:02d}, administrador HU-A01..HU-A{n_admin:02d}."""

# from_messages([...]) construye la plantilla de chat a partir de una lista de
# tuplas (rol, texto). Aquí hay 2 mensajes:
#   ("system", SYSTEM)      -> instrucciones persistentes del asistente
#   ("human", ...)          -> petición corta de ejecución del usuario
# El resultado es un Runnable: se compone con | y se invoca con un dict de
# variables ({app_name, context, n_*, temas_*}).
GENERATE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM),
        ("human", "Genera ahora las historias en el formato JSON indicado, una por cada tema listado."),
    ]
)

# prompts.py: Define las plantillas de prompts para cada cadena LLM.
# Lógica: cada prompt es un ChatPromptTemplate que combina un mensaje de sistema
# (con las instrucciones del analista) y un mensaje humano (con los datos).
# IMPORTANTE: no usar llaves literales {} en los textos, porque LangChain las
# interpreta como variables. Usa {variable} para inyectar datos.

"""Prompts como ChatPromptTemplate. No usar llaves literales dentro de los textos."""
from langchain_core.prompts import ChatPromptTemplate  # Plantilla de prompts para chat

# _BASE: instrucción base que se repite en TODOS los prompts del sistema.
# Sintaxis: tupla de strings que se concatenan con +.
# Lógica: define el "rol" del LLM (analista de requisitos senior) y reglas
# generales (responder en español, no inventar requisitos, etc.).
# {context} se inyecta dinámicamente con el contexto del proyecto.
_BASE = (
    "Eres un analista de requisitos senior con experiencia en Scrum y Product Ownership. "
    "Respondes SIEMPRE en español, de forma estricta, concreta y sin inventar requisitos "
    "que no estén en la historia. Si algo no aparece en la historia, dilo; no lo supongas.\n\n"
    "Contexto del proyecto:\n{context}\n"
)

# ANALYSIS_PROMPT: prompt para descomponer la historia en rol/acción/beneficio.
# Sintaxis: ChatPromptTemplate.from_messages() crea una plantilla desde una lista de tuplas.
# Cada tupla es (tipo_mensaje, contenido). "system" = instrucción, "human" = entrada del usuario.
# Lógica: le pide al LLM que confirme si es historia de usuario y extraiga sus partes.
# {story} = historia limpia, {warnings} = advertencias del prevalidador.
ANALYSIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            _BASE
            + "\nTarea: descompón la historia de usuario en rol, acción y beneficio. "
            "Marca es_historia_usuario=false si el texto es una tarea técnica, un requisito "
            "no funcional suelto, una idea vaga sin usuario o algo que no describe una necesidad "
            "de un usuario. Deja vacío el campo que no aparezca de forma explícita.",
        ),
        (
            "human",
            "Historia:\n{story}\n\n"
            "Advertencias del prevalidador automático (pueden ser falsas):\n{warnings}",
        ),
    ]
)

# RELEVANCE_PROMPT: prompt para verificar si la historia es relevante para el proyecto.
# Sintaxis: mismo patrón que los otros prompts.
# Lógica: evalúa si la historia está relacionada con el dominio, objetivos y alcances del proyecto.
# Si la historia no tiene nada que ver, se rechaza antes de gastar tokens en INVEST/ambigüedad.
# {story} = historia limpia.
RELEVANCE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            _BASE
            + "\nTarea: evalúa si la siguiente historia de usuario es relevante para el proyecto "
            "descrito en el contexto. Considera:\n"
            "- El dominio del proyecto (qué tipo de aplicación es)\n"
            "- Los objetivos del proyecto (qué quiere lograr)\n"
            "- Los alcances (qué funcionalidades incluye)\n"
            "- Los roles de usuario que maneja el proyecto\n\n"
            "Asigna un puntaje de relevancia del 0 al 10:\n"
            "- 0-2: nada que ver con el proyecto (ej: historia de una app dedelivery en un proyecto de busetas)\n"
            "- 3-5: relacionada tangencialmente pero no es funcionalidad core\n"
            "- 6-8: relevante, pertenece a un área del proyecto\n"
            "- 9-10: funcionalidad central del proyecto\n\n"
            "Si es relevante, indica a qué área pertenece (rutas, horarios, GPS, planificación, etc.).",
        ),
        (
            "human",
            "Historia:\n{story}",
        ),
    ]
)

# INVEST_PROMPT: prompt para evaluar la historia contra los 6 criterios INVEST.
# Lógica: le pide al LLM que puntúe cada criterio de 1 a 5 y justifique.
# Los criterios son: Independent, Negotiable, Valuable, Estimable, Small, Testable.
# {story}, {rol}, {accion}, {beneficio} se inyectan desde el estado.
INVEST_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            _BASE
            + "\nTarea: evalúa la historia con el modelo INVEST. Puntúa cada criterio de 1 a 5 "
            "(1 = incumple totalmente, 3 = cumple parcialmente, 5 = cumple plenamente). "
            "Sé estricto: un 5 es raro.\n"
            "- Independent: puede desarrollarse y entregarse sin depender de otra historia.\n"
            "- Negotiable: describe el QUÉ y deja abierto el CÓMO (sin imponer tecnología ni diseño).\n"
            "- Valuable: el beneficio es claro y le importa al usuario o al negocio.\n"
            "- Estimable: el equipo tiene información suficiente para estimar el esfuerzo.\n"
            "- Small: cabe en una iteración; no es una épica disfrazada.\n"
            "- Testable: se puede verificar con criterios objetivos de aceptación.\n"
            "Cada justificación: máximo dos frases. Cada sugerencia: una mejora concreta.",
        ),
        (
            "human",
            "Historia:\n{story}\n\n"
            "Descomposición previa -> rol: {rol} | acción: {accion} | beneficio: {beneficio}",
        ),
    ]
)

# AMBIGUITY_PROMPT: prompt para detectar ambigüedades en la historia.
# Lógica: busca adjetivos subjetivos, cantidades sin definir, pronombres sin referente, etc.
# Por cada ambigüedad: cita el fragmento, explica el problema y formula una pregunta.
# Clasifica el nivel: baja (0-1 menor), media (1-2 relevantes), alta (2+ que impiden implementar).
# {story}, {vague_terms} se inyectan desde el estado.
AMBIGUITY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            _BASE
            + "\nTarea: detecta ambigüedades en la historia: adjetivos subjetivos (rápido, fácil), "
            "cantidades sin definir (algunos, varios), actores imprecisos, pronombres sin referente, "
            "condiciones sin límite y términos que dos personas interpretarían distinto. "
            "Por cada una cita el fragmento EXACTO, explica el problema y formula una pregunta "
            "aclaratoria para el Product Owner. Nivel: baja (0 o 1 ambigüedad menor), media (1 a 2 relevantes), "
            "alta (2 o más que impiden implementar o probar la historia). "
            "Si no hay ambigüedades, devuelve la lista vacía y nivel baja.",
        ),
        (
            "human",
            "Historia:\n{story}\n\n"
            "Términos vagos detectados automáticamente (pueden ser falsos positivos):\n{vague_terms}",
        ),
    ]
)

# CRITERIA_PROMPT: prompt para generar criterios de aceptación en formato Gherkin.
# Lógica: genera entre 3 y 5 escenarios que cubran: flujo principal, caso de error,
# caso límite. Cada "Entonces" debe ser observable y verificable.
# No inventa funcionalidades fuera de la historia.
# {story}, {ambiguities} se inyectan desde el estado.
CRITERIA_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            _BASE
            + "\nTarea: escribe criterios de aceptación en formato Gherkin en español "
            "(Dado / Cuando / Entonces). Entre 3 y 5 escenarios que cubran: el flujo principal, "
            "al menos un caso de error o dato inválido y al menos un caso límite. "
            "Cada 'Entonces' debe ser observable y verificable (nada de 'funciona bien'). "
            "No inventes funcionalidades fuera de la historia. Si hay ambigüedades pendientes, "
            "no las resuelvas por tu cuenta: escribe el criterio sobre lo que sí está claro.",
        ),
        (
            "human",
            "Historia:\n{story}\n\n"
            "Ambigüedades pendientes (no las supongas):\n{ambiguities}",
        ),
    ]
)

# REWRITE_PROMPT: prompt para reescribir la historia y que cumpla INVEST.
# Lógica: conserva la intención original, elimina implementación y términos vagos.
# Si es demasiado grande, quédate con la parte más valiosa y menciona el resto
# en preguntas_pendientes. Lista en 'cambios' qué se modificó y por qué.
# {story}, {weak_points}, {ambiguities} se inyectan desde el estado.
REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            _BASE
            + "\nTarea: reescribe la historia para que sea INVEST. Formato obligatorio: "
            "'Como [rol], quiero [acción], para [beneficio]'. Conserva la intención original, "
            "elimina detalles de implementación y términos vagos, y no agregues funcionalidades nuevas. "
            "Si la historia original es demasiado grande, quédate con la parte más valiosa y "
            "menciona el resto en preguntas_pendientes. Lista en 'cambios' qué modificaste y por qué.",
        ),
        (
            "human",
            "Historia original:\n{story}\n\n"
            "Puntos débiles INVEST:\n{weak_points}\n\n"
            "Ambigüedades detectadas:\n{ambiguities}",
        ),
    ]
)

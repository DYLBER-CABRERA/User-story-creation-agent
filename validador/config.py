# Docstring del módulo: describe el propósito general del archivo.
# Sintaxis: triple comilla doble para docstring multilínea.
# Lógica: centraliza TODA la configuración en un solo lugar, leyendo de
# variables de entorno (o un archivo .env). Sigue el patrón "12-Factor App"
# para separar configuración del código fuente.
"""Configuración centralizada, leída desde variables de entorno / .env."""

# from __future__ import annotations: import especial de Python 3.7+ (PEP 563).
# Sintaxis: se importa "desde el futuro" del módulo __future__.
# Lógica: pospone la evaluación de las anotaciones de tipo (tipo hints)
# a modo de cadenas, permitiendo usar tipos modernos como list[str],
# tuple[str, ...] o str | None sin errores en versiones viejas de Python.
from __future__ import annotations

# import os: importa el módulo estándar del sistema operativo.
# Sintaxis: import simple.
# Lógica: se usa para acceder a variables de entorno del sistema
# mediante os.getenv(). Es la forma estándar de leer configuración
# externa sin hardcodear valores en el código.
import os

# from dataclasses import dataclass: importa el decorador dataclass.
# Sintaxis: importa solo la función/módulo específico que se necesita.
# Lógica: un dataclass genera automáticamente __init__, __repr__,
# __eq__ y otros métodos. Es perfecto para clases que son "contenedores
# de datos" como esta de configuración, ahorrando mucho boilerplate.
from dataclasses import dataclass

# from dotenv import load_dotenv: importa la función load_dotenv.
# Sintaxis: importa de la librería externa python-dotenv.
# Lógica: esta función lee un archivo .env (si existe en la raíz del
# proyecto) y carga sus variables al entorno del proceso (os.environ).
# Así puedes definir GOOGLE_API_KEY=abc123 en .env sin exponerlo
# en el código fuente (no se sube a git).
from dotenv import load_dotenv

# load_dotenv(): llamada a función sin argumentos.
# Sintaxis: función ejecutada a nivel de módulo (se ejecuta 1 vez al importar).
# Lógica: busca automáticamente un archivo .env en el directorio de trabajo
# actual y carga todas sus variables al os.environ. Se hace aquí porque
# cualquier archivo que haga "from config import Settings" ya necesitará
# las variables del .env cargadas antes de leerlas.
load_dotenv()


# @dataclass(frozen=True): decorador que convierte la clase en un dataclass.
# Sintaxis: @ es el decorador, frozen=True es un parámetro del decorador.
# Lógica: frozen=True hace que la instancia sea INMUTABLE una vez creada.
# Nadie puede hacer settings.temperature = 1.0 después de la construcción.
# Esto es CRUCIAL para configuración: evita que algún módulo accidentalmente
# modifique los valores globales durante la ejecución. También hace que
# el objeto sea hashable (puede usarse como clave de diccionario o en sets).
@dataclass(frozen=True)
class Settings:
    # Campo: google_api_key de tipo str.
    # Sintaxis: anotación de tipo con : str. No tiene valor por defecto.
    # Lógica: almacena la API key de Google/Gemini. Es str porque puede
    # ser una cadena vacía "" si no se configura. El get_settings() le
    # asigna un default vía os.getenv con default "".
    google_api_key: str

    # Campo: gemini_model de tipo str.
    # Sintaxis: mismo patrón de anotación.
    # Lógica: nombre del modelo de Google Gemini a usar (ej: "gemini-2.5-flash").
    # Permite cambiar el modelo sin modificar código fuente.
    gemini_model: str

    # Campo: ollama_model de tipo str.
    # Sintaxis: str simple.
    # Lógica: nombre del modelo local de Ollama (ej: "qwen2.5:3b").
    # Ollama corre en localhost y sirve como respaldo cuando Gemini
    # no está disponible (sin API key, sin red, cuota agotada).
    ollama_model: str

    # Campo: ollama_base_url de tipo str.
    # Sintaxis: str simple.
    # Lógica: URL base del servidor Ollama (por defecto http://localhost:11434).
    # Permite apuntar a un Ollama remoto si se despliega en otro servidor
    # o en un contenedor Docker.
    ollama_base_url: str

    # Campo: provider_order de tipo tuple[str, ...].
    # Sintaxis: tuple[str, ...] = tupla de strings de longitud arbitraria.
    # Lógica: define el orden de preferencia de proveedores LLM.
    # Ej: ("gemini", "ollama") = "intentar Gemini primero, si falla usar Ollama".
    # Se guarda como tupla (inmutable) en vez de lista porque la
    # configuración no debería cambiar después de creada.
    provider_order: tuple[str, ...]

    # Campo: temperature de tipo float.
    # Sintaxis: float = número decimal.
    # Lógica: controla la "temperatura" del LLM.
    # 0 = respuestas deterministas (siempre la más probable).
    # Valores altos (0.7-1.0) = más creatividad/aleatoriedad.
    # Para un validador de historias de usuario, 0 es lo correcto:
    # necesitas respuestas consistentes y reproducibles.
    temperature: float

    # Campo: timeout_s de tipo int.
    # Sintaxis: int = entero. El sufijo _s es una convención de nombrado.
    # Lógica: tiempo máximo de espera (en SEGUNDOS) para las respuestas del LLM.
    # Si Gemini tarda más de 60 segundos, el sistema usa el respaldo (Ollama).
    timeout_s: int

    # Campo: approve_threshold de tipo float.
    # Sintaxis: float decimal.
    # Lógica: umbral mínimo para que una historia sea APROBADA directamente.
    # Si el puntaje promedio INVEST >= 4.0, la historia pasa sin reescritura.
    # Es el punto de corte "estricto" del sistema de validación.
    approve_threshold: float

    # Campo: project_context de tipo str.
    # Sintaxis: str simple.
    # Lógica: contexto descriptivo del proyecto (dominio, objetivos, alcances).
    # Se usa como fallback cuando el usuario no pasa project_context al grafo.
    # También se inyecta en los prompts del LLM para que entienda el dominio.
    project_context: str

    # Campo: min_threshold de tipo float.
    # Sintaxis: float decimal.
    # Lógica: umbral mínimo para que una historia NO sea RECHAZADA.
    # Si el puntaje está entre min_threshold (3.0) y approve_threshold (4.0),
    # la historia requiere reescritura. Si está por debajo de 3.0, se rechaza.
    # Define la línea entre "se puede mejorar" y "no sirve".
    min_threshold: float


# get_settings(): factory function (fábrica) que construye y retorna Settings.
# Sintaxis: función con retorno tipado -> Settings. Sin parámetros de entrada.
# Lógica: en vez de hardcodear la configuración en la clase, esta función
# la lee de las variables de entorno. Es la ÚNICA forma de crear un objeto
# Settings válido. Si no se define la variable, usa un default razonable.
def get_settings() -> Settings:
    # Lee la cadena de proveedores del entorno. Si no existe, usa "gemini,ollama".
    # Sintaxis: os.getenv(var, default) retorna el valor de la variable o el default.
    # Lógica: es una cadena separada por comas que luego se parsea en tupla.
    order = os.getenv("PROVIDER_ORDER", "gemini,ollama")

    # Retorna una instancia de Settings con todos los campos.
    # Sintaxis: return + Settings() llama al __init__ generado por @dataclass.
    # Lógica: construye el objeto completo con todos los valores leídos del entorno.
    return Settings(
        # os.getenv("GOOGLE_API_KEY", ""): lee la API key, default vacío.
        # .strip(): elimina espacios accidentales al inicio/final.
        # Lógica: si alguien pegó " AIzaSy... " con espacios, .strip() los limpia.
        google_api_key=os.getenv("GOOGLE_API_KEY", "").strip(),

        # Lee el nombre del modelo Gemini, default "gemini-2.5-flash".
        # Lógica: modelo rápido y barato de Google. El usuario puede cambiarlo
        # a "gemini-2.5-pro" o cualquier otro modelo vigente en la documentación.
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),

        # Lee el nombre del modelo Ollama, default "qwen2.5:3b".
        # Lógica: modelo de 3B parámetros, cabe en GPUs de 4GB.
        # Es el respaldo cuando Gemini falla (sin API key, sin red, cuota agotada).
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),

        # Lee la URL de Ollama, default "http://localhost:11434".
        # Lógica: puerto estándar de Ollama. Si se despliega en Docker
        # o un servidor remoto, se cambia esta URL en el .env.
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),

        # Parsea la cadena de proveedores a una tupla normalizada.
        # Sintaxis: tuple() + expresión generadora + encadenamiento de métodos.
        # order.split(","): divide "gemini,ollama" en ["gemini", "ollama"].
        # .strip(): elimina espacios alrededor de cada nombre.
        # .lower(): normaliza a minúsculas.
        # if p.strip(): filtra entradas vacías (ej: si hay coma doble).
        # Lógica: convierte "gemini, ollama" en ("gemini", "ollama").
        provider_order=tuple(p.strip().lower() for p in order.split(",") if p.strip()),

        # float(os.getenv(...)): convierte el string del entorno a decimal.
        # Lógica: temperatura 0 = respuestas deterministas. Si se quiere
        # creatividad, se pone "0.7" por ejemplo en el .env.
        temperature=float(os.getenv("LLM_TEMPERATURE", "0")),

        # int(os.getenv(...)): convierte el string del entorno a entero.
        # Lógica: timeout de 60 segundos. Si el LLM no responde en ese
        # tiempo, se considera fallo y se usa el respaldo (Ollama).
        timeout_s=int(os.getenv("LLM_TIMEOUT", "60")),

        # float(os.getenv(...)): convierte a decimal.
        # Lógica: puntaje INVEST promedio >= 4.0 = historia aprobada
        # directamente. Se puede ajustar según la estricta que se quiera
        # la validación (4.0 es el default "razonable").
        approve_threshold=float(os.getenv("APPROVE_THRESHOLD", "4.0")),

        # Lee el contexto del proyecto. Si no existe, usa un default genérico.
        # Lógica: es la descripción del proyecto que se inyecta en cada prompt del LLM.
        project_context=os.getenv("PROJECT_CONTEXT", "Aplicación para consultar rutas, horarios y ubicación de las busetas."),

        # float(os.getenv(...)): convierte a decimal.
        # Lógica: puntaje INVEST promedio >= 3.0 = historia aceptable
        # (con reescritura). Por debajo de 3.0 = rechazada.
        # Define el piso mínimo de calidad.
        min_threshold=float(os.getenv("MIN_THRESHOLD", "3.0")),
    )

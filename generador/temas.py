"""Temas por defecto, tomados del documento de Alcances del proyecto.

Asignar un tema distinto y obligatorio a cada historia es lo que evita que el
modelo local "rellene" la cantidad pedida repitiendo la misma idea: en vez de
dejarle la diversidad a su criterio, se la damos ya resuelta.

Los temas cubren exactamente las funcionalidades definidas en el alcance del
proyecto (docs/contexto-busetasapp.md). El número de historias por rol queda
determinado por la cantidad de temas: el agente no necesita que el usuario le
indique cuántas generar.
"""

TEMAS_PASAJERO = [
    "Visualizar la disponibilidad de rutas y paradas en el mapa",
    "Ver el recorrido de una ruta dibujado en el mapa",
    "Consultar horarios y días de operación de una ruta",
    "Ver la frecuencia de paso de las busetas por franja horaria",
    "Ver la ubicación en tiempo real de las busetas (GPS)",
    "Conocer el tiempo estimado de llegada (ETA) a una parada",
    "Planificar un viaje indicando origen y destino",
    "Buscar rutas por número o nombre de ruta",
    "Buscar rutas por barrio, sector o punto de interés (hitos urbanos como Catedral, El Cable, Fundadores)",
    "Guardar rutas o paradas como favoritas",
    "Recibir una notificación cuando la buseta esté por llegar a una parada de interés",
    "Usar la app sin necesidad de crear una cuenta",
]

TEMAS_JEFE_OPERACIONES = [
    "Asignar conductores y busetas a rutas ya registradas en la plataforma",
    "Ingresar datos de rutas de forma manual en la plataforma",
    "Subir un archivo Excel con los datos de rutas y conductores",
    "Definir el rodamiento del día (ruta, hora de salida, buseta y conductor)",
    "Publicar avisos generales de la empresa (cambios de ruta, suspensiones, horarios de festivos)",
    "Consultar estadísticas básicas de uso de la app para su empresa",
]

TEMAS_SECRETARIA_MOVILIDAD = [
    "Registrar una nueva ruta y asignarla a una empresa",
    "Editar los datos de una ruta existente en la plataforma",
    "Eliminar una ruta de la plataforma",
    "Gestionar los paraderos de la ciudad (agregar, editar, eliminar)",
    "Registrar un cambio de movilidad en la ciudad (cierre, desvío, obra, condición vial)",
]

TEMAS_ADMINISTRADOR = [
    "Gestionar los usuarios de la plataforma (crear, editar, desactivar)",
    "Gestionar roles y permisos de acceso",
    "Gestionar las empresas de busetas registradas en la plataforma",
    "Configurar parámetros globales de la plataforma",
    "Publicar avisos sobre el aplicativo (mantenimiento, actualizaciones, incidencias)",
]

TEMAS_POR_ROL = {
    "pasajero": TEMAS_PASAJERO,
    "jefe_operaciones": TEMAS_JEFE_OPERACIONES,
    "secretaria_movilidad": TEMAS_SECRETARIA_MOVILIDAD,
    "administrador": TEMAS_ADMINISTRADOR,
}


def temas_para(rol: str, cantidad: int | None = None) -> list[str]:
    """Devuelve los temas para el rol.

    Si `cantidad` es None (por defecto), devuelve TODOS los temas definidos para
    ese rol: el agente genera exactamente una historia por cada funcionalidad del
    alcance, sin que el usuario tenga que indicar cuántas quiere.

    Si se pasa `cantidad`, devuelve esa cantidad de temas. Si se piden más de los
    disponibles, repite el ciclo marcando "(variante N)" para que sigan siendo
    instrucciones distintas entre sí, aunque partan del mismo tema base.
    """
    base = TEMAS_POR_ROL[rol]
    if cantidad is None:
        return list(base)
    if cantidad <= len(base):
        return base[:cantidad]
    out = list(base)
    i = 0
    while len(out) < cantidad:
        out.append(f"{base[i % len(base)]} (variante {i // len(base) + 2})")
        i += 1
    return out


def formatear(temas: list[str]) -> str:
    return "\n".join(f"{i}. {t}" for i, t in enumerate(temas, 1))

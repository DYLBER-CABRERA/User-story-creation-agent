"""Temas por defecto, tomados del documento de Alcances del proyecto.

Asignar un tema distinto y obligatorio a cada historia es lo que evita que el
modelo local "rellene" la cantidad pedida repitiendo la misma idea: en vez de
dejarle la diversidad a su criterio, se la damos ya resuelta.
"""
# a esto se le llama grounding (anclaje) y es una técnica de prompt engineering que ayuda a que el modelo genere respuestas más coherentes y consistentes, al proporcionarle un contexto claro y específico y
# no se invente cosas que no están en los alcances del proyecto. En este caso, los temas son el contexto que le damos al modelo para que genere historias de usuario coherentes y consistentes con el proyecto.
TEMAS_PASAJERO = [
    "Visualizar las disponibilidad de rutas y paradas en el mapa",
    "Ver el recorrido de una ruta dibujado en el mapa",
    "Consultar horarios y días de operación de una ruta",
    "Ver la ubicación en tiempo real de las busetas (GPS)",
    "Conocer el tiempo estimado de llegada (ETA) a una parada",
    "Planificar un viaje indicando origen y destino",
    "Buscar rutas por barrio o punto de interés",
    "Guardar rutas o paradas como favoritas",
    "Recibir una notificación cuando la buseta esté por llegar",
    "Usar la app sin necesidad de crear una cuenta",
]

TEMAS_CONDUCTOR = [
    "Comenzar el recorrido de una ruta (compartir ubicación)",
    "Finalizar el recorrido (dejar de compartir ubicación)",
    "Reportar una novedad en la vía (desvío, accidente, cierre)",
]

TEMAS_ADMINISTRADOR = [
    "Crear, editar y eliminar rutas con su trazado y paradas",
    "Registrar y modificar horarios y días de operación",
    "Registrar busetas y asignarlas a rutas y conductores",
    "Publicar avisos generales (cambios, suspensiones, festivos)",
    "Ver estadísticas básicas de uso de la app",
]

TEMAS_POR_ROL = {
    "pasajero": TEMAS_PASAJERO,
    "conductor": TEMAS_CONDUCTOR,
    "administrador": TEMAS_ADMINISTRADOR,
}


def temas_para(rol: str, cantidad: int) -> list[str]:
    """Devuelve `cantidad` temas para el rol. Si se piden más de los disponibles,
    repite el ciclo marcando "(variante N)" para que sigan siendo instrucciones
    distintas entre sí, aunque partan del mismo tema base."""
    base = TEMAS_POR_ROL[rol]
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

"""Temas por defecto, tomados del documento de Alcances del proyecto.

Lógica central:
  Asignar un tema distinto y obligatorio a cada historia es lo que evita que el
  modelo local "rellene" la cantidad pedida repitiendo la misma idea: en vez de
  dejarle la diversidad a su criterio, se la damos ya resuelta.
"""


# Constantes de módulo en MAYÚSCULAS: convención de Python para "no reasignar".
# Cada lista es el catálogo de temas disponibles por rol (orden fijo = orden del
# documento de Alcances). La longitud define el máximo "natural" sin repeticiones.
TEMAS_PASAJERO = [
    "Consultar el catálogo de rutas disponibles",
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

# 5 temas de conductor; si se piden más, temas_para() aplica variantes.
TEMAS_CONDUCTOR = [
    "Iniciar sesión y comenzar el recorrido de una ruta (compartir ubicación)",
    "Finalizar el recorrido (dejar de compartir ubicación)",
    "Ver la ruta y las paradas asignadas antes de salir",
    "Reportar una novedad en la vía (desvío, accidente, cierre)",
    "Recibir aviso de la próxima parada programada",
]

# 5 temas de administrador; misma lógica de variantes si se excede.
TEMAS_ADMINISTRADOR = [
    "Crear, editar y eliminar rutas con su trazado y paradas",
    "Registrar y modificar horarios y días de operación",
    "Registrar busetas y asignarlas a rutas y conductores",
    "Publicar avisos generales (cambios, suspensiones, festivos)",
    "Ver estadísticas básicas de uso de la app",
]

# Diccionario (hash map) de lookup O(1): rol (str) -> lista de temas.
# La clave debe ser exactamente "pasajero" | "conductor" | "administrador".
TEMAS_POR_ROL = {
    "pasajero": TEMAS_PASAJERO,
    "conductor": TEMAS_CONDUCTOR,
    "administrador": TEMAS_ADMINISTRADOR,
}


def temas_para(rol: str, cantidad: int) -> list[str]:
    """Devuelve `cantidad` temas para el rol. Si se piden más de los disponibles,
    repite el ciclo marcando "(variante N)" para que sigan siendo instrucciones
    distintas entre sí, aunque partan del mismo tema base.

    Lógica:
      - cantidad <= len(base): rebanada base[:cantidad] (slice hasta la posición
        pedida, sin incluir el índice cantidad) -> temas 100 % originales.
      - cantidad > len(base): copia la base completa y sigue agregando
        copias rotuladas con variante.
    """
    base = TEMAS_POR_ROL[rol]  # KeyError si el rol no existe (falla explícito)
    if cantidad <= len(base):
        return base[:cantidad]  # slice -> nueva lista con los primeros N
    out = list(base)  # copia superficial (shallow copy) de la lista base
    i = 0  # índice que recorre la base cíclicamente
    while len(out) < cantidad:  # mientras falten temas por agregar
        # i % len(base) -> posición dentro de la base (0,1,2,...,0,1,...)
        # i // len(base) + 2 -> número de variante: en la 2ª pasada empieza en 2
        out.append(f"{base[i % len(base)]} (variante {i // len(base) + 2})")
        i += 1
    return out  # lista exactamente de tamaño `cantidad`, toda entrada distinta


def formatear(temas: list[str]) -> str:
    """Convierte la lista en una enumeración numerada de una línea por tema.

    enumerate(temas, 1) -> pares (índice empezando en 1, tema).
    La comprensión genera strings "1. tema"; "\n".join(...) los une con saltos
    de línea -> formato listo para insertar en el prompt.
    """
    return "\n".join(f"{i}. {t}" for i, t in enumerate(temas, 1))

"""Esquema de salida: una sola llamada al LLM devuelve las tres listas completas.

Lógica central:
  - Pydantic valida la respuesta del modelo AL CONSTRUIR el objeto.
  - Si hay dos historias con el mismo "quiero" dentro de un rol, el validador
    lanza ValueError -> Pydantic lo envuelve en ValidationError -> LangChain
    lo detecta y with_retry reintenta (ver generar.py).
"""
from __future__ import annotations  # anotaciones de tipo perezosas (compatibilidad)

# BaseModel: clase base de Pydantic v2 -> define el "contrato" de cada campo.
# Field: metadatos por campo (description se usa como esquema para el LLM).
# model_validator(mode="after"): hook que corre DESPUÉS de construir el modelo,
# permitiendo validar relaciones entre campos (aquí: unicidad dentro de cada lista).
from pydantic import BaseModel, Field, model_validator


class HistoriaUsuario(BaseModel):
    """Una historia de usuario individual. El LLM debe llenar los 4 campos."""
    id: str = Field(description="Identificador corto, ej: HU-P01")
    rol: str = Field(description="Pasajero, Conductor o Administrador")
    como: str = Field(description="El rol, tal como iría después de 'Como'.")
    quiero: str = Field(description="La acción, tal como iría después de 'quiero'.")
    para: str = Field(description="El beneficio, tal como iría después de 'para'.")

    # @property -> convierte el método en atributo de sólo lectura: h.texto
    # se accede sin paréntesis (h.texto, no h.texto()).
    # f-string: interpola valores; se ejecuta en cada acceso, no guarda estado.
    @property
    def texto(self) -> str:
        """Arma la línea final exacta que ve el usuario/backlog."""
        return f"{self.id}: Como {self.como}, quiero {self.quiero}, para {self.para}."


def _normalizar(txt: str) -> str:
    """Normaliza para comparar: minúsculas + colapsa espacios múltiples.

    lower() -> todo a minúsculas; split() -> lista de palabras (espacios simples
    ya normalizados); " ".join(...) -> recompone con un solo espacio entre palabras.
    Así "Ver  RUTAS " y "ver rutas" se consideran iguales.
    """
    return " ".join(txt.lower().split())


def _sin_duplicados(lista: list[HistoriaUsuario], rol: str) -> None:
    """Recorre la lista y lanza ValueError si dos historias comparten 'quiero'.

    vistos: dict mapea clave normalizada -> id de la primera historia que la usó.
    Al ser dict, la inserción es O(1); el recorrido completo es O(n).
    raise ValueError(...) detiene la validación -> Pydantic lo convierte en
    ValidationError en el contexto del model_validator.
    """
    vistos: dict[str, str] = {}
    for h in lista:  # itera cada HistoriaUsuario de la lista del rol
        clave = _normalizar(h.quiero)  # clave comparable de la acción
        if clave in vistos:  # ya vimos este "quiero" antes en ESTE rol
            raise ValueError(
                f"Historias repetidas en {rol}: '{h.id}' y '{vistos[clave]}' tienen el mismo 'quiero'."
            )
        vistos[clave] = h.id  # registra la primera aparición de esta clave
    # Si sale del for sin raise, no hay duplicados -> validación OK.


class HistoriasGeneradas(BaseModel):
    """Salida completa del LLM: las tres listas por rol."""
    pasajero: list[HistoriaUsuario]         # lista tipada: cada elemento debe ser HistoriaUsuario
    conductor: list[HistoriaUsuario]
    administrador: list[HistoriaUsuario]

    # mode="after" -> corre una vez construidos los tres campos; si lanza,
    # Pydantic descarta el objeto entero y emite ValidationError.
    @model_validator(mode="after")
    def _validar_sin_repetidos(self):
        """Aplica la regla de unicidad a CADA rol por separado.

        Nota: model_construct() (usado en tests) SALTAN los validadores,
        lo que permite fabricar un objeto inválido a propósito para probar
        que with_retry reacciona al ValidationError de la construcción normal.
        """
        _sin_duplicados(self.pasajero, "pasajero")
        _sin_duplicados(self.conductor, "conductor")
        _sin_duplicados(self.administrador, "administrador")
        return self  # el validator "after" debe devolver la instancia para aceptarla

    def todas(self) -> list[HistoriaUsuario]:
        """Aplana las tres listas en una sola (orden: pasajero, conductor, admin).

        [*a, *b, *c] -> unpacking: copia los elementos de cada iterable
        en una nueva lista literal.
        """
        return [*self.pasajero, *self.conductor, *self.administrador]

"""Esquema de salida: una sola llamada al LLM devuelve las cuatro listas completas.

HistoriasGeneradas valida que no haya historias duplicadas (mismo "quiero") dentro
de un mismo rol. Si el LLM repite, Pydantic rechaza la salida y el `with_retry` de
generar.py fuerza un reintento en vez de dejar pasar historias repetidas.

Cada historia incluye (según la guía del Specification Agent):
- flujo_normal / flujo_alternativo / flujo_excepcion
  (sección 2.3: camino exitoso, alternativas válidas y excepciones por fallo)
- criterios Dado/Cuando/Entonces    (sección 2.5: criterios de aceptación verificables)

Roles (4): Pasajero, Jefe de Operaciones, Secretaría de Movilidad, Administrador.
El rol Conductor fue eliminado del alcance (contexto-busetasapp.md §4).
"""
from __future__ import annotations

import unicodedata

from pydantic import BaseModel, Field, model_validator


class CriterioAceptacion(BaseModel):
    """Criterio de aceptación en formato Dado / Cuando / Entonces (Given-When-Then)."""
    dado: str = Field(description="Precondición observable, ej: 'el pedido está pendiente de aceptación'")
    cuando: str = Field(description="Acción del actor, ej: 'el cliente solicita cancelarlo'")
    entonces: str = Field(description="Resultado esperado y observable, ej: 'el sistema cancela el pedido y notifica al cliente'")

    @property
    def texto(self) -> str:
        return f"Dado {self.dado}, cuando {self.cuando}, entonces {self.entonces}."


class HistoriaUsuario(BaseModel):
    id: str = Field(description="Identificador corto, ej: HU-P01")
    rol: str = Field(description="Pasajero, Jefe de Operaciones, Secretaría de Movilidad o Administrador")
    como: str = Field(description="El rol, tal como iría después de 'Como'.")
    quiero: str = Field(description="La acción, tal como iría después de 'quiero'.")
    para: str = Field(description="El beneficio, tal como iría después de 'para'.")
    flujo_normal: list[str] = Field(
        min_length=1,
        description="Pasos cortos del camino exitoso, ej: ['el pasajero busca una ruta', 'el sistema muestra las rutas']",
    )
    flujo_alternativo: list[str] = Field(
        min_length=1,
        description="Al menos 1 alternativa válida (sin resultados, cancelación, dato inválido), "
                    "ej: ['no hay resultados', 'el sistema informa que no hay rutas']",
    )
    flujo_excepcion: list[str] = Field(
        min_length=1,
        description="Al menos 1 excepción por fallo con su manejo (sin conexión, servicio no "
                    "disponible, timeout), ej: ['la app pierde la conexión', 'el sistema muestra un "
                    "aviso y reintenta']",
    )
    criterios: list["CriterioAceptacion"] = Field(
        min_length=1,
        description="1 o 2 criterios de aceptación verificables en Dado/Cuando/Entonces",
    )

    @property
    def texto(self) -> str:
        return f"{self.id}: Como {self.como}, quiero {self.quiero}, para {self.para}."

    @model_validator(mode="after")
    def _como_es_el_rol(self):
        """'como' debe ser SOLO el rol. Modelos como los de Groq tienden a meter la
        acción ahí ("Como Quiero visualizar…"): Pydantic lo rechaza y with_retry
        fuerza un reintento en vez de entregar la historia mal formada."""
        if _clave(self.como) != _clave(self.rol):
            raise ValueError(
                f"el campo 'como' debe ser el rol '{self.rol}' (llegó: '{self.como}')"
            )
        return self

    @property
    def detalle(self) -> str:
        """Historia completa con flujos y criterios (para exportación y consola)."""
        lineas = [self.texto, "  Flujo normal: " + " -> ".join(self.flujo_normal),
                  "  Flujo alternativo: " + " -> ".join(self.flujo_alternativo),
                  "  Flujo de excepción: " + " -> ".join(self.flujo_excepcion)]
        lineas.extend(f"  CA-{i}: {c.texto}" for i, c in enumerate(self.criterios, 1))
        return "\n".join(lineas)


def _normalizar(txt: str) -> str:
    return " ".join(txt.lower().split())


def _sin_tildes(txt: str) -> str:
    """Elimina diacríticos para comparación robusta (secretaría == secretaria)."""
    nfd = unicodedata.normalize("NFD", txt)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _clave(txt: str) -> str:
    """Clave de comparación de rol: minúsculas, sin espacios sobrantes, sin tildes, sin punto final."""
    return _sin_tildes(_normalizar(txt)).rstrip(". ")


def _sin_duplicados(lista: list[HistoriaUsuario], rol: str) -> None:
    vistos: dict[str, str] = {}
    for h in lista:
        clave = _normalizar(h.quiero)
        if clave in vistos:
            raise ValueError(
                f"Historias repetidas en {rol}: '{h.id}' y '{vistos[clave]}' tienen el mismo 'quiero'."
            )
        vistos[clave] = h.id


class RnfEspec(BaseModel):
    """Propuesta de RNF para una funcionalidad (1-13). El equipo la confirma al
    aprobar la SPEC: una propuesta del agente no es una decisión (guía §2.2/§8)."""

    num: int = Field(ge=1, le=13, description="Número de la SPEC/funcionalidad (1 a 13)")
    rendimiento_s: float = Field(
        gt=0, description="Segundos máximos de respuesta de la operación principal"
    )
    disponibilidad_pct: float = Field(
        gt=0, le=100, description="Porcentaje mínimo de disponibilidad (ventana mensual)"
    )
    actualizacion_min: float = Field(
        gt=0, description="Minutos máximos de cadencia de actualización de datos"
    )


class HistoriasGeneradas(BaseModel):
    pasajero: list[HistoriaUsuario]
    jefe_operaciones: list[HistoriaUsuario]
    secretaria_movilidad: list[HistoriaUsuario]
    administrador: list[HistoriaUsuario]
    rnf_especs: list[RnfEspec] = Field(
        default_factory=list,
        description=(
            "Una propuesta de RNF por funcionalidad (num 1-13). Opcional: si no "
            "se incluye, los valores RNF quedan pendientes de propuesta."
        ),
    )

    @model_validator(mode="after")
    def _validar_sin_repetidos(self):
        _sin_duplicados(self.pasajero, "pasajero")
        _sin_duplicados(self.jefe_operaciones, "jefe_operaciones")
        _sin_duplicados(self.secretaria_movilidad, "secretaria_movilidad")
        _sin_duplicados(self.administrador, "administrador")
        return self

    @model_validator(mode="after")
    def _validar_roles_de_cada_lista(self):
        """Cada historia debe llevar el rol de su lista: si 'rol' o 'como' no
        coinciden con la columna, la salida se rechaza y se reintenta."""
        for lista, esperado in (
            (self.pasajero, "pasajero"),
            (self.jefe_operaciones, "jefe de operaciones"),
            (self.secretaria_movilidad, "secretaria de movilidad"),
            (self.administrador, "administrador"),
        ):
            for h in lista:
                if _clave(h.rol) != esperado:
                    raise ValueError(
                        f"{h.id}: en la lista '{esperado}' el rol vino como '{h.rol}'"
                    )
        return self

    def todas(self) -> list[HistoriaUsuario]:
        return [*self.pasajero, *self.jefe_operaciones, *self.secretaria_movilidad, *self.administrador]

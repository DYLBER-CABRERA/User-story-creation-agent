"""Esquema de salida: una sola llamada al LLM devuelve las tres listas completas.

HistoriasGeneradas valida que no haya historias duplicadas (mismo "quiero") dentro
de un mismo rol. Si el LLM repite, Pydantic rechaza la salida y el `with_retry` de
generar.py fuerza un reintento en vez de dejar pasar historias repetidas.

Cada historia incluye (según la guía del Specification Agent):
- flujo_normal / flujo_alternativo / flujo_excepcion
  (sección 2.3: camino exitoso, alternativas válidas y excepciones por fallo)
- criterios Dado/Cuando/Entonces    (sección 2.5: criterios de aceptación verificables)
"""
from __future__ import annotations

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
    rol: str = Field(description="Pasajero, Conductor o Administrador")
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


def _sin_duplicados(lista: list[HistoriaUsuario], rol: str) -> None:
    vistos: dict[str, str] = {}
    for h in lista:
        clave = _normalizar(h.quiero)
        if clave in vistos:
            raise ValueError(
                f"Historias repetidas en {rol}: '{h.id}' y '{vistos[clave]}' tienen el mismo 'quiero'."
            )
        vistos[clave] = h.id


class HistoriasGeneradas(BaseModel):
    pasajero: list[HistoriaUsuario]
    conductor: list[HistoriaUsuario]
    administrador: list[HistoriaUsuario]

    @model_validator(mode="after")
    def _validar_sin_repetidos(self):
        _sin_duplicados(self.pasajero, "pasajero")
        _sin_duplicados(self.conductor, "conductor")
        _sin_duplicados(self.administrador, "administrador")
        return self

    def todas(self) -> list[HistoriaUsuario]:
        return [*self.pasajero, *self.conductor, *self.administrador]

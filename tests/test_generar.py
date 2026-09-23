"""Pruebas del generador con LLM SIMULADO (no se llama a Ollama ni a Gemini).

Estrategia:
  - FakeLLM / RunnableLambda reemplazan al modelo real dentro de la MISMA
    composición LCEL (GENERATE_PROMPT | fake.with_structured_output(...)),
    así se prueba build_chain y generar_historias de punta a punta sin red.
  - Se prueba la regla de negocio crítica: Pydantic rechaza duplicados y
    with_retry reintenta hasta obtener una salida limpia.
"""
# pytest: framework de pruebas; raises(...) verifica que se lance una excepción
import pytest
# RunnableLambda: envuelve una función simple como Runnable de LCEL,
# para que fake tenga la misma interfaz (with_structured_output -> Runnable)
from langchain_core.runnables import RunnableLambda
# ValidationError: el error concreto que lanza Pydantic ante un modelo inválido
from pydantic import ValidationError

# Import de las unidades bajo prueba (build_chain, generar_historias) y
# de los objetos de dominio (HistoriaUsuario, HistoriasGeneradas) y temas
from generador.generar import build_chain, generar_historias
from generador.schemas import HistoriaUsuario, HistoriasGeneradas
from generador.temas import formatear, temas_para


def mk(i, rol, pfx, quiero=None):
    """Fábrica de HistoriaUsuario válidos para las pruebas.

    - i: número secuencial (define el ID HU-P01, HU-C01...).
    - rol: "Pasajero" | "Conductor" | "Administrador".
    - pfx: prefijo del ID (P/C/A).
    - quiero: si se pasa, TODAS las historias con ese valor quedan idénticas
      en la acción -> simula el fallo real de historias repetidas.
    - Por defecto cada historia es única ("hacer algo N"); pasa `quiero` fijo para simular duplicados.
    - :02d -> formatea el entero i con mínimo 2 dígitos y ceros a la izquierda
      (1 -> "01").
    """
    return HistoriaUsuario(
        id=f"HU-{pfx}{i:02d}", rol=rol, como=rol.lower(),
        # Ternario: quiero si se pasó, si no "hacer algo {i}" único por i
        quiero=quiero if quiero is not None else f"hacer algo {i}",
        para="lograr un beneficio",
    )


class FakeLLM:
    """Doble de prueba: devuelve respuestas precargadas en orden (FIFO).

    Implementa el mínimo interfaz que usa build_chain:
      llm.with_structured_output(schema) -> Runnable que ignora el input
      y hace pop(0) de la siguiente respuesta.
    """

    def __init__(self, respuestas):
        # list(...) copia defensiva: no mutar la lista del caller
        self.respuestas = list(respuestas)

    def with_structured_output(self, schema):
        """Igual firma que el método real de LangChain (schema se ignora aquí)."""
        def run(_):
            # pop(0): saca y devuelve la PRIMERA respuesta pendiente;
            # si no queda, lanza IndexError (útil para detectar llamadas de más)
            return self.respuestas.pop(0)

        # RunnableLambda convierte `run` en un Runnable componible con |
        return RunnableLambda(run)


def historias_ok():
    """Salida válida y completa: 6 pasajeros, 5 conductores, 4 administradores."""
    return HistoriasGeneradas(
        # Comprensión de lista: range(1, 7) = 1..6 inclusive del límite superior
        pasajero=[mk(i, "Pasajero", "P") for i in range(1, 7)],
        conductor=[mk(i, "Conductor", "C") for i in range(1, 6)],
        administrador=[mk(i, "Administrador", "A") for i in range(1, 5)],
    )


def historias_repetidas():
    """Salida INVÁLIDA a propósito: dos pasajeros con el mismo 'quiero'.

    model_construct(...) SALTAN los validadores de Pydantic -> permite
    construir un objeto que la validación normal rechazaría (útil para
    tests de retry que necesitan simular la respuesta corrupta del LLM
    sin que falle en el momento de fabricar el objeto de prueba).
    """
    return HistoriasGeneradas.model_construct(
        pasajero=[mk(1, "Pasajero", "P", quiero="ver horarios"), mk(2, "Pasajero", "P", quiero="ver horarios")],
        conductor=[],
        administrador=[],
    )


def test_genera_cantidades_exactas():
    """generar_historias respeta 6/5/4 con una cadena fake (sin red)."""
    # Import local: mantiene el test acoplado al prompt real del proyecto
    from generador.prompts import GENERATE_PROMPT
    # Composición idéntica a la real, pero con FakeLLM en vez de ChatOllama
    chain = GENERATE_PROMPT | FakeLLM([historias_ok()]).with_structured_output(HistoriasGeneradas)
    out, secs = generar_historias(chain=chain)  # chain inyectada => no toca .env/red
    # assert: si falla, pytest marca el test como roto
    assert len(out.pasajero) == 6
    assert len(out.conductor) == 5
    assert len(out.administrador) == 4
    assert secs >= 0  # la duración es un float >= 0 segundos


def test_formato_texto():
    """La property .texto arma EXACTAMENTE la línea del backlog."""
    h = HistoriaUsuario(id="HU-P01", rol="Pasajero", como="pasajero", quiero="ver rutas", para="saber cuáles hay")
    # Cadena literal exacta: id + dos puntos + "Como..., quiero..., para...."
    assert h.texto == "HU-P01: Como pasajero, quiero ver rutas, para saber cuáles hay."


def test_todas_junta_las_listas():
    """todas() aplana las tres listas (con conductores/admin vacíos también)."""
    hg = HistoriasGeneradas(
        pasajero=[HistoriaUsuario(id="1", rol="p", como="p", quiero="a", para="b")],
        conductor=[],
        administrador=[],
    )
    assert len(hg.todas()) == 1  # 1 + 0 + 0 = 1


def test_pydantic_rechaza_historias_repetidas():
    """Si el LLM devuelve dos 'quiero' iguales en un rol, ValidationError."""
    # pytest.raises(cm): el bloque WITH debe lanzar esa excepción;
    # si NO lanza, el test falla (regla de negocio protegida)
    with pytest.raises(ValidationError):
        HistoriasGeneradas(
            # Ambas pasajeras con "ver horarios" -> dispara _sin_duplicados
            pasajero=[mk(1, "Pasajero", "P", quiero="ver horarios"), mk(2, "Pasajero", "P", quiero="ver horarios")],
            conductor=[],
            administrador=[],
        )


def test_with_retry_reintenta_si_hay_repetidas():
    """Primera respuesta viene con duplicados (simulando el fallo real reportado);
    la segunda viene limpia. build_chain debe reintentar sola y devolver la buena."""
    # dict mutable para contar invocaciones: `calls` se cierra por referencia
    # (las closures de Python ven el objeto original, no una copia)
    calls = {"n": 0}

    class LLMConDuplicadoLuegoBueno:
        """LLM de prueba: 1ª llamada responde mal, 2ª bien."""

        def with_structured_output(self, schema):
            def run(_):
                calls["n"] += 1  # incrementa el contador de llamadas
                if calls["n"] == 1:
                    # Igual que con un LLM real: construir el modelo dispara los
                    # validadores de Pydantic -> ValidationError -> with_retry reintenta.
                    # Nota: aquí SÍ usamos el constructor normal (no model_construct)
                    # para que el ValidationError se lance de verdad dentro de run()
                    return HistoriasGeneradas(
                        pasajero=[mk(1, "Pasajero", "P", quiero="ver horarios"),
                                  mk(2, "Pasajero", "P", quiero="ver horarios")],
                        conductor=[], administrador=[],
                    )
                return historias_ok()  # 2ª llamada: salida válida
            return RunnableLambda(run)

    # build_chain recibe proveedores inyectados: [(nombre, llm)] sin tocar .env
    chain = build_chain([("ollama", LLMConDuplicadoLuegoBueno())])
    out, _ = generar_historias(chain=chain)  # _ descarta la duración
    assert len(out.pasajero) == 6  # resultado final = la respuesta buena
    assert calls["n"] == 2  # confirma que sí reintentó (1 fallo + 1 OK)


def test_temas_por_defecto_no_se_repiten():
    """Dentro del catálogo base, los N primeros temas son únicos."""
    # set(...) elimina duplicados: si el set mantiene N elementos, no había repetidos
    assert len(set(temas_para("pasajero", 6))) == 6
    assert len(set(temas_para("conductor", 5))) == 5


def test_temas_piden_mas_de_los_disponibles():
    """Si se piden más temas que el catálogo, se agregan variantes únicas."""
    temas = temas_para("pasajero", 12)  # catálogo tiene 10 -> 2 variantes extra
    assert len(temas) == 12  # cantidad exacta pedida
    assert len(set(temas)) == 12  # con "(variante N)" siguen siendo distintos como texto
    # enumerate(..., 1) hace que la enumeración empiece en 1: "1. ", "2. "...
    assert formatear(temas[:2]).startswith("1. ")

import pytest
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from generador.generar import build_chain, generar_historias
from generador.schemas import CriterioAceptacion, HistoriaUsuario, HistoriasGeneradas
from generador.temas import formatear, temas_para


def mk(i, rol, pfx, quiero=None):
    # Por defecto cada historia es única ("hacer algo N"); pasa `quiero` fijo para simular duplicados.
    return HistoriaUsuario(
        id=f"HU-{pfx}{i:02d}", rol=rol, como=rol.lower(),
        quiero=quiero if quiero is not None else f"hacer algo {i}",
        para="lograr un beneficio",
        flujo_normal=[f"{rol.lower()} realiza la acción", "el sistema responde con el resultado"],
        flujo_alternativo=[f"{rol.lower()} no tiene resultados", "el sistema informa el motivo"],
        flujo_excepcion=[f"falla el servicio para {rol.lower()}", "el sistema muestra un aviso reintentable"],
        criterios=[CriterioAceptacion(
            dado=f"el {rol.lower()} está en la app",
            cuando=f"el {rol.lower()} ejecuta la acción {i}",
            entonces=f"el sistema muestra el resultado {i}",
        )],
    )


class FakeLLM:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)

    def with_structured_output(self, schema):
        def run(_):
            return self.respuestas.pop(0)

        return RunnableLambda(run)


def historias_ok():
    return HistoriasGeneradas(
        pasajero=[mk(i, "Pasajero", "P") for i in range(1, 7)],
        conductor=[mk(i, "Conductor", "C") for i in range(1, 6)],
        administrador=[mk(i, "Administrador", "A") for i in range(1, 5)],
    )


def historias_repetidas():
    return HistoriasGeneradas.model_construct(
        pasajero=[mk(1, "Pasajero", "P", quiero="ver horarios"), mk(2, "Pasajero", "P", quiero="ver horarios")],
        conductor=[],
        administrador=[],
    )


def test_genera_cantidades_exactas():
    from generador.prompts import GENERATE_PROMPT
    chain = GENERATE_PROMPT | FakeLLM([historias_ok()]).with_structured_output(HistoriasGeneradas)
    out, secs = generar_historias(chain=chain)
    assert len(out.pasajero) == 6
    assert len(out.conductor) == 5
    assert len(out.administrador) == 4
    assert secs >= 0


def test_formato_texto():
    h = mk(1, "Pasajero", "P")
    assert h.texto == "HU-P01: Como pasajero, quiero hacer algo 1, para lograr un beneficio."


def test_historia_exige_flujos_y_criterios():
    """Sin flujo_normal / flujo_alternativo / flujo_excepcion / criterios, Pydantic rechaza."""
    with pytest.raises(ValidationError):
        HistoriaUsuario(id="HU-P01", rol="Pasajero", como="pasajero",
                        quiero="ver rutas", para="saber cuáles hay")
    with pytest.raises(ValidationError):
        HistoriaUsuario(**{**mk(1, "Pasajero", "P").model_dump(), "criterios": []})
    with pytest.raises(ValidationError):
        HistoriaUsuario(**{**mk(1, "Pasajero", "P").model_dump(), "flujo_normal": []})
    with pytest.raises(ValidationError):
        HistoriaUsuario(**{**mk(1, "Pasajero", "P").model_dump(), "flujo_excepcion": []})


def test_criterio_formato_dado_cuando_entonces():
    c = CriterioAceptacion(dado="el pedido está pendiente de aceptación",
                           cuando="el cliente solicita cancelarlo",
                           entonces="el sistema cancela el pedido y notifica al cliente")
    assert c.texto == ("Dado el pedido está pendiente de aceptación, cuando el cliente "
                       "solicita cancelarlo, entonces el sistema cancela el pedido y notifica al cliente.")


def test_detalle_incluye_flujos_y_criterios():
    h = mk(1, "Pasajero", "P")
    assert "Flujo normal:" in h.detalle
    assert "Flujo alternativo:" in h.detalle
    assert "Flujo de excepción:" in h.detalle
    assert "CA-1:" in h.detalle
    assert "Dado" in h.detalle


def test_todas_junta_las_listas():
    hg = HistoriasGeneradas(
        pasajero=[mk(1, "Pasajero", "P")],
        conductor=[],
        administrador=[],
    )
    assert len(hg.todas()) == 1


def test_pydantic_rechaza_historias_repetidas():
    with pytest.raises(ValidationError):
        HistoriasGeneradas(
            pasajero=[mk(1, "Pasajero", "P", quiero="ver horarios"), mk(2, "Pasajero", "P", quiero="ver horarios")],
            conductor=[],
            administrador=[],
        )


def test_with_retry_reintenta_si_hay_repetidas():
    """Primera respuesta viene con duplicados (simulando el fallo real reportado);
    la segunda viene limpia. build_chain debe reintentar sola y devolver la buena."""
    calls = {"n": 0}

    class LLMConDuplicadoLuegoBueno:
        def with_structured_output(self, schema):
            def run(_):
                calls["n"] += 1
                if calls["n"] == 1:
                    # Igual que con un LLM real: construir el modelo dispara los
                    # validadores de Pydantic -> ValidationError -> with_retry reintenta.
                    return HistoriasGeneradas(
                        pasajero=[mk(1, "Pasajero", "P", quiero="ver horarios"),
                                  mk(2, "Pasajero", "P", quiero="ver horarios")],
                        conductor=[], administrador=[],
                    )
                return historias_ok()
            return RunnableLambda(run)

    chain = build_chain([("ollama", LLMConDuplicadoLuegoBueno())])
    out, _ = generar_historias(chain=chain)
    assert len(out.pasajero) == 6
    assert calls["n"] == 2  # confirma que sí reintentó


def _historia_corta():
    """Respuesta de modelo que 'se rinde': solo 2 por rol en vez de 6/5/4."""
    return HistoriasGeneradas(
        pasajero=[mk(1, "Pasajero", "P"), mk(2, "Pasajero", "P")],
        conductor=[mk(1, "Conductor", "C"), mk(2, "Conductor", "C")],
        administrador=[mk(1, "Administrador", "A"), mk(2, "Administrador", "A")],
    )


def test_reintenta_si_el_modelo_viene_corto():
    """Primera respuesta con 2/2/2 historias -> se detecta, se reintenta y la segunda
    llega completa (6/5/4). Nunca se entrega una lista corta en silencio."""
    llamadas = {"n": 0}

    class ChainCortaLuegoCompleta:
        def invoke(self, payload):
            llamadas["n"] += 1
            return _historia_corta() if llamadas["n"] == 1 else historias_ok()

    out, _ = generar_historias(chain=ChainCortaLuegoCompleta())
    assert len(out.pasajero) == 6
    assert len(out.conductor) == 5
    assert len(out.administrador) == 4
    assert llamadas["n"] == 2


def test_error_explicito_si_persisten_incompletas():
    """Si siempre vuelve corta, error con el detalle de conteos (nunca resultado a medias)."""

    class ChainSiempreCorta:
        def invoke(self, payload):
            return _historia_corta()

    with pytest.raises(RuntimeError, match="pasajero: 2/6"):
        generar_historias(chain=ChainSiempreCorta())


def test_temas_por_defecto_no_se_repiten():
    assert len(set(temas_para("pasajero", 6))) == 6
    assert len(set(temas_para("conductor", 5))) == 5


def test_temas_piden_mas_de_los_disponibles():
    temas = temas_para("pasajero", 12)
    assert len(temas) == 12
    assert len(set(temas)) == 12  # con "(variante N)" siguen siendo distintos como texto
    assert formatear(temas[:2]).startswith("1. ")

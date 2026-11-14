import pytest
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from generador.generar import build_chain, generar_historias
from generador.schemas import CriterioAceptacion, HistoriaUsuario, HistoriasGeneradas
from generador.temas import formatear, temas_para, TEMAS_POR_ROL


def mk(i, rol, pfx, quiero=None):
    # Por defecto cada historia es unica ("hacer algo N"); pasa `quiero` fijo para simular duplicados.
    return HistoriaUsuario(
        id=f"HU-{pfx}{i:02d}", rol=rol, como=rol.lower(),
        quiero=quiero if quiero is not None else f"hacer algo {i}",
        para="lograr un beneficio",
        flujo_normal=[f"{rol.lower()} realiza la accion", "el sistema responde con el resultado"],
        flujo_alternativo=[f"{rol.lower()} no tiene resultados", "el sistema informa el motivo"],
        flujo_excepcion=[f"falla el servicio para {rol.lower()}", "el sistema muestra un aviso reintentable"],
        criterios=[CriterioAceptacion(
            dado=f"el {rol.lower()} esta en la app",
            cuando=f"el {rol.lower()} ejecuta la accion {i}",
            entonces=f"el sistema muestra el resultado {i}",
        )],
    )


N_PASAJERO = len(TEMAS_POR_ROL["pasajero"])
N_JEFE = len(TEMAS_POR_ROL["jefe_operaciones"])
N_SECRETARIA = len(TEMAS_POR_ROL["secretaria_movilidad"])
N_ADMIN = len(TEMAS_POR_ROL["administrador"])


class FakeLLM:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)

    def with_structured_output(self, schema):
        def run(_):
            return self.respuestas.pop(0)

        return RunnableLambda(run)


def historias_ok():
    return HistoriasGeneradas(
        pasajero=[mk(i, "Pasajero", "P") for i in range(1, N_PASAJERO + 1)],
        jefe_operaciones=[mk(i, "Jefe de Operaciones", "J") for i in range(1, N_JEFE + 1)],
        secretaria_movilidad=[mk(i, "Secretaria de Movilidad", "SM") for i in range(1, N_SECRETARIA + 1)],
        administrador=[mk(i, "Administrador", "A") for i in range(1, N_ADMIN + 1)],
    )


def test_genera_cantidades_exactas():
    from generador.prompts import GENERATE_PROMPT
    chain = GENERATE_PROMPT | FakeLLM([historias_ok()]).with_structured_output(HistoriasGeneradas)
    out, secs = generar_historias(chain=chain)
    assert len(out.pasajero) == N_PASAJERO
    assert len(out.jefe_operaciones) == N_JEFE
    assert len(out.secretaria_movilidad) == N_SECRETARIA
    assert len(out.administrador) == N_ADMIN
    assert secs >= 0


def test_debug_prompt_imprime_prompt_y_tiempos(capsys):
    """--debug-prompt: el prompt exacto (contexto ya interpolado) y el tiempo por intento."""
    from generador.prompts import GENERATE_PROMPT
    chain = GENERATE_PROMPT | FakeLLM([historias_ok()]).with_structured_output(HistoriasGeneradas)
    generar_historias(chain=chain, debug=True)
    err = capsys.readouterr().err
    assert "PROMPT EXACTO" in err
    assert "Contexto de la app:" in err
    assert "----- system" in err and "----- human" in err
    assert "[intento 1] respuesta del modelo en " in err
    assert "conteos ok" in err
    assert "FIN PROMPT" in err

    chain2 = GENERATE_PROMPT | FakeLLM([historias_ok()]).with_structured_output(HistoriasGeneradas)
    generar_historias(chain=chain2)
    assert capsys.readouterr().err == ""


def test_formato_texto():
    h = mk(1, "Pasajero", "P")
    assert h.texto == "HU-P01: Como pasajero, quiero hacer algo 1, para lograr un beneficio."


def test_historia_exige_flujos_y_criterios():
    """Sin flujo_normal / flujo_alternativo / flujo_excepcion / criterios, Pydantic rechaza."""
    with pytest.raises(ValidationError):
        HistoriaUsuario(id="HU-P01", rol="Pasajero", como="pasajero",
                        quiero="ver rutas", para="saber cuales hay")
    with pytest.raises(ValidationError):
        HistoriaUsuario(**{**mk(1, "Pasajero", "P").model_dump(), "criterios": []})
    with pytest.raises(ValidationError):
        HistoriaUsuario(**{**mk(1, "Pasajero", "P").model_dump(), "flujo_normal": []})
    with pytest.raises(ValidationError):
        HistoriaUsuario(**{**mk(1, "Pasajero", "P").model_dump(), "flujo_excepcion": []})


def test_como_debe_ser_el_rol_no_la_accion():
    """Los modelos de Groq tienden a meter la accion en 'como' ("Como Quiero
    visualizar..."); Pydantic lo rechaza y with_retry fuerza el reintento."""
    with pytest.raises(ValidationError, match="como"):
        HistoriaUsuario(**{**mk(1, "Pasajero", "P").model_dump(),
                           "como": "Quiero visualizar las rutas"})
    # historia con el rol equivocado dentro de su lista tambien se rechaza
    with pytest.raises(ValidationError, match="en la lista 'pasajero'"):
        HistoriasGeneradas(
            pasajero=[mk(1, "Jefe de Operaciones", "P")],
            jefe_operaciones=[], secretaria_movilidad=[], administrador=[],
        )


def test_criterio_formato_dado_cuando_entonces():
    c = CriterioAceptacion(dado="el pedido esta pendiente de aceptacion",
                           cuando="el cliente solicita cancelarlo",
                           entonces="el sistema cancela el pedido y notifica al cliente")
    assert c.texto == ("Dado el pedido esta pendiente de aceptacion, cuando el cliente "
                       "solicita cancelarlo, entonces el sistema cancela el pedido y notifica al cliente.")


def test_detalle_incluye_flujos_y_criterios():
    h = mk(1, "Pasajero", "P")
    assert "Flujo normal:" in h.detalle
    assert "Flujo alternativo:" in h.detalle
    assert "excepci" in h.detalle  # "Flujo de excepción:" (con o sin tilde)
    assert "CA-1:" in h.detalle
    assert "Dado" in h.detalle


def test_todas_junta_las_listas():
    hg = HistoriasGeneradas(
        pasajero=[mk(1, "Pasajero", "P")],
        jefe_operaciones=[],
        secretaria_movilidad=[],
        administrador=[],
    )
    assert len(hg.todas()) == 1


def test_pydantic_rechaza_historias_repetidas():
    with pytest.raises(ValidationError):
        HistoriasGeneradas(
            pasajero=[mk(1, "Pasajero", "P", quiero="ver horarios"),
                      mk(2, "Pasajero", "P", quiero="ver horarios")],
            jefe_operaciones=[], secretaria_movilidad=[], administrador=[],
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
                    return HistoriasGeneradas(
                        pasajero=[mk(1, "Pasajero", "P", quiero="ver horarios"),
                                  mk(2, "Pasajero", "P", quiero="ver horarios")],
                        jefe_operaciones=[], secretaria_movilidad=[], administrador=[],
                    )
                return historias_ok()
            return RunnableLambda(run)

    chain = build_chain([("ollama", LLMConDuplicadoLuegoBueno())])
    out, _ = generar_historias(chain=chain)
    assert len(out.pasajero) == N_PASAJERO
    assert calls["n"] == 2


def _historia_corta():
    """Respuesta de modelo que 'se rinde': solo 2 por rol."""
    return HistoriasGeneradas(
        pasajero=[mk(1, "Pasajero", "P"), mk(2, "Pasajero", "P")],
        jefe_operaciones=[mk(1, "Jefe de Operaciones", "J"), mk(2, "Jefe de Operaciones", "J")],
        secretaria_movilidad=[mk(1, "Secretaria de Movilidad", "SM")],
        administrador=[mk(1, "Administrador", "A"), mk(2, "Administrador", "A")],
    )


def test_reintenta_si_el_modelo_viene_corto():
    """Primera respuesta corta -> se detecta, se reintenta y la segunda llega completa."""
    llamadas = {"n": 0}

    class ChainCortaLuegoCompleta:
        def invoke(self, payload):
            llamadas["n"] += 1
            return _historia_corta() if llamadas["n"] == 1 else historias_ok()

    out, _ = generar_historias(chain=ChainCortaLuegoCompleta())
    assert len(out.pasajero) == N_PASAJERO
    assert len(out.jefe_operaciones) == N_JEFE
    assert len(out.secretaria_movilidad) == N_SECRETARIA
    assert len(out.administrador) == N_ADMIN
    assert llamadas["n"] == 2


def test_error_explicito_si_persisten_incompletas():
    """Si siempre vuelve corta, error con el detalle de conteos."""

    class ChainSiempreCorta:
        def invoke(self, payload):
            return _historia_corta()

    with pytest.raises(RuntimeError, match="pasajero"):
        generar_historias(chain=ChainSiempreCorta())


def test_temas_por_defecto_no_se_repiten():
    assert len(set(temas_para("pasajero"))) == N_PASAJERO
    assert len(set(temas_para("jefe_operaciones"))) == N_JEFE
    assert len(set(temas_para("secretaria_movilidad"))) == N_SECRETARIA
    assert len(set(temas_para("administrador"))) == N_ADMIN


def test_temas_piden_mas_de_los_disponibles():
    temas = temas_para("pasajero", N_PASAJERO + 5)
    assert len(temas) == N_PASAJERO + 5
    assert len(set(temas)) == N_PASAJERO + 5  # con "(variante N)" siguen siendo distintos
    assert formatear(temas[:2]).startswith("1. ")


def test_temas_sin_cantidad_devuelve_todos():
    """temas_para sin cantidad devuelve todos los temas del rol (comportamiento por defecto)."""
    assert temas_para("pasajero") == temas_para("pasajero", N_PASAJERO)
    assert temas_para("jefe_operaciones") == temas_para("jefe_operaciones", N_JEFE)

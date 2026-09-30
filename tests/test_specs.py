from generador.specs import (
    ALCANCE_PATH,
    CATALOGO,
    _leer_alcance,
    aprobar,
    cargar_control,
    construir_specs,
    congelar,
    contexto_proyecto,
    detectar_cambios,
    escribir_specs,
    guardar_control,
    preguntas_generadas,
    preguntas_pendientes,
    registrar_respuesta,
    seleccionar,
    spec_de_historia,
)
from tests.test_generar import historias_ok

VACIO = {"respuestas": {}, "estados": {}, "eventos": []}


def test_mapeo_historia_a_spec():
    # pasajero: temas 1-2 -> SPEC 001, tema 3 -> 002, tema 8 -> 008...
    assert spec_de_historia("pasajero", 0) == 1
    assert spec_de_historia("pasajero", 2) == 2
    assert spec_de_historia("pasajero", 3) == 3
    assert spec_de_historia("pasajero", 7) == 8
    assert spec_de_historia("pasajero", 9) == 10
    # variante del tema 1 (índice 10) sigue en la SPEC 001
    assert spec_de_historia("pasajero", 10) == 1
    assert spec_de_historia("conductor", 4) == 7
    assert spec_de_historia("administrador", 3) == 11
    assert spec_de_historia("administrador", 4) == 12


def test_son_12_specs_y_cada_una_tiene_las_17_secciones():
    docs = construir_specs(None, control=VACIO)
    assert len(docs) == 12 == len(CATALOGO)
    for d in docs:
        for n in range(1, 18):
            assert f"## {n}." in d.markdown, f"{d.titulo} sin sección {n}"
        assert "pendiente de aprobación humana" in d.markdown


def test_spec_con_historias_incluye_rf_flujos_ac_y_trazabilidad():
    docs = construir_specs(historias_ok(), control=VACIO)
    spec1 = next(d for d in docs if d.num == 1)   # HU-P01 y HU-P02 caen en 001
    assert "RF-001-01" in spec1.markdown and "HU-P01" in spec1.markdown
    assert "RF-001-02" in spec1.markdown and "HU-P02" in spec1.markdown
    assert "AC-001-01" in spec1.markdown
    assert "Dado" in spec1.markdown                 # criterios Dado/Cuando/Entonces
    assert "Flujo" in spec1.markdown
    assert "(alternativo)" in spec1.markdown        # §9 distingue alternativa y excepción
    assert "(excepción)" in spec1.markdown
    assert "| HU-P01 | RF-001-01" in spec1.markdown  # tabla §16
    # SPEC sin historias en esta corrida -> pendiente
    spec8 = next(d for d in docs if d.num == 8)
    assert "Pendiente" in spec8.markdown


def test_spec_sin_historias_marca_pendientes():
    docs = construir_specs(None, control=VACIO)
    d = docs[0]
    assert "sin historias asignadas" in d.markdown
    # §6 RNF se lee de la §14 del alcance; los valores faltantes quedan marcados
    assert "| RNF-01 |" in d.markdown and "[por definir]" in d.markdown
    assert "SUG-RNF** (§15)" in d.markdown


def test_reglas_y_fuera_de_alcance_vienen_del_documento():
    docs = construir_specs(None, control=VACIO)
    spec6 = next(d for d in docs if d.num == 6)
    assert "BR-03" in spec6.markdown
    assert "Solo el administrador crea" in spec6.markdown        # §7 alcance
    spec1 = next(d for d in docs if d.num == 1)
    assert "Pago de pasajes" in spec1.markdown                     # §6 alcance en §14
    assert "8 semanas" in spec1.markdown                         # §12 alcance en §13


def test_seleccionar_por_numero_o_slug():
    docs = construir_specs(None, control=VACIO)
    assert len(seleccionar(docs, "all")) == 12
    assert [d.num for d in seleccionar(docs, "003")] == [3]
    assert [d.num for d in seleccionar(docs, "3")] == [3]
    assert [d.num for d in seleccionar(docs, "rutas")] == [1]
    assert seleccionar(docs, "no-existe") == []


def test_escribir_specs_en_carpeta(tmp_path):
    docs = construir_specs(None, control=VACIO)
    rutas = escribir_specs(docs, tmp_path)
    assert len(rutas) == 12
    assert (tmp_path / "SPEC-001-consulta-de-rutas.md").exists()
    assert (tmp_path / "SPEC-012-estadisticas-basicas.md").exists()
    contenido = (tmp_path / "SPEC-001-consulta-de-rutas.md").read_text(encoding="utf-8")
    assert "## 17. Historial de cambios" in contenido


# ── control humano (guía §11-§12) ──────────────────────────────────────

def _control_vacio():
    return {"respuestas": {}, "estados": {}, "eventos": []}


def test_respuestas_se_reflejan_en_seccion_15():
    control = _control_vacio()
    pend = preguntas_pendientes(control)
    assert len(pend) >= 3                      # OPEN-Q-001..003 del alcance
    assert registrar_respuesta(control, "OPEN-Q-001", "Se cargan manualmente", "Profesor")
    assert not registrar_respuesta(control, "OPEN-Q-999", "no existe")
    docs = construir_specs(None, control=control)
    d = docs[0]
    assert "OPEN-Q-001** — **Respondida** (Profesor" in d.markdown
    assert "Se cargan manualmente" in d.markdown
    assert "OPEN-Q-002** — **Pendiente**" in d.markdown
    assert len(preguntas_pendientes(control)) >= 2


def test_aprobar_bloqueado_por_preguntas_pendientes():
    control = _control_vacio()
    ok, msg = aprobar(control, 1, "Profe")
    assert not ok
    assert "OPEN-Q-001" in msg and "§12" in msg
    assert control.get("estados", {}) == {}    # nada cambió


def test_aprobar_congelar_cambian_estado_version_e_historial():
    control = _control_vacio()
    for q in preguntas_pendientes(control, spec_num=1):
        registrar_respuesta(control, q["id"], f"Decisión sobre {q['id']}", "Profe")

    ok, msg = aprobar(control, 1, "Profe")
    assert ok and "APROBADA v1.0" in msg
    docs = construir_specs(None, control=control)
    assert "APROBADA v1.0" in docs[0].markdown
    assert "pendiente de aprobación humana" not in docs[0].markdown
    assert "| 1.0 |" in docs[0].markdown        # historial registra aprobación

    ok2, _ = aprobar(control, 1, "Otro")         # doble aprobación falla
    assert not ok2

    ok3, msg3 = congelar(control, 1)
    assert ok3 and "FROZEN" in msg3
    docs = construir_specs(None, control=control)
    assert "FROZEN (congelada) v1.0" in docs[0].markdown

    ok4, _ = congelar(control, 1)                # doble congelación falla
    assert not ok4


def test_no_congelar_sin_aprobar():
    control = _control_vacio()
    ok, msg = congelar(control, 2)
    assert not ok and "aprobada" in msg
    assert control.get("estados", {}).get("002") is None


def test_control_se_persiste_en_archivo(tmp_path):
    ruta = tmp_path / "control.json"
    control = _control_vacio()
    guardar_control(control, ruta)
    cargado = cargar_control(ruta)
    assert cargado["estados"] == {} and cargado["eventos"] == []
    registrar_respuesta(cargado, "OPEN-Q-001", "texto", "Profe")
    guardar_control(cargado, ruta)
    assert "OPEN-Q-001" in cargar_control(ruta)["respuestas"]
    assert cargar_control(tmp_path / "no-existe.json")["estados"] == {}


# ── §5 pasos 5-6: preguntas sugeridas por el agente ────────────────────

def test_preguntas_sugeridas_por_el_agente():
    control = _control_vacio()
    pend = preguntas_pendientes(control, spec_num=1)
    ids = [q["id"] for q in pend]
    assert {"SUG-RNF", "SUG-001-CASOS", "SUG-001-DEP"} <= set(ids)

    docs = construir_specs(None, control=control)
    md = docs[0].markdown
    assert "Preguntas sugeridas por el agente" in md and "SUG-RNF" in md
    assert "SUG-001-CASOS" not in docs[4].markdown   # las sugerencias son por SPEC

    for q in pend:
        assert registrar_respuesta(control, q["id"], f"ok: {q['id']}", "Profe")
    assert not [q for q in preguntas_pendientes(control, spec_num=1)
                if str(q["id"]).startswith("SUG-")]
    assert not registrar_respuesta(control, "SUG-XXX", "id inexistente")


def test_respuestas_de_sugerencias_alimentan_las_secciones():
    control = _control_vacio()
    assert registrar_respuesta(control, "SUG-RNF", "Máximo 2 s, 99% disponibilidad", "Profe")
    md = construir_specs(None, control=control)[0].markdown
    sec6 = md.split("## 6.")[1].split("## 7.")[0]
    assert "| RNF-01 |" in sec6                       # la tabla viene del alcance §14
    assert "Máximo 2 s" in sec6 and "Pendiente:" not in sec6
    assert "SUG-RNF** — **Respondida** (Profe" in md


def test_rnf_con_valores_definidos_no_genera_pregunta(tmp_path):
    """Si el equipo define todos los valores en §14, desaparece SUG-RNF y §6 queda limpia."""
    original = ALCANCE_PATH.read_text(encoding="utf-8")
    definido = original.replace("**[por definir]**", "2 s con 100 usuarios")
    ruta = tmp_path / "alcance.md"
    ruta.write_text(definido, encoding="utf-8")

    secciones = _leer_alcance(ruta)
    assert not [q for q in preguntas_generadas(1, secciones) if q["id"] == "SUG-RNF"]
    control = _control_vacio()
    control["respuestas"] = {
        "OPEN-Q-001": {"respuesta": "x", "responsable": "P", "fecha": "2026-01-01"},
        "OPEN-Q-002": {"respuesta": "x", "responsable": "P", "fecha": "2026-01-01"},
        "OPEN-Q-003": {"respuesta": "x", "responsable": "P", "fecha": "2026-01-01"},
        "SUG-001-CASOS": {"respuesta": "x", "responsable": "P", "fecha": "2026-01-01"},
        "SUG-001-DEP": {"respuesta": "x", "responsable": "P", "fecha": "2026-01-01"},
    }
    docs = construir_specs(None, alcance_path=ruta, control=control)
    sec6 = docs[0].markdown.split("## 6.")[1].split("## 7.")[0]
    assert "| RNF-01 |" in sec6 and "[por definir]" not in sec6
    # sin decisión abierta: no hay fila SUG-RNF pendiente en la §15
    assert "**SUG-RNF** — **Pendiente**" not in docs[0].markdown
    # SUG-RNF desaparece de las pendientes globales (CLI --responder sin SPEC)
    control2 = _control_vacio()
    control2["respuestas"] = control["respuestas"] | {
        f"SUG-{n:03d}-CASOS": {"respuesta": "x", "responsable": "P", "fecha": "2026-01-01"}
        for n in range(1, 13)
    } | {
        f"SUG-{n:03d}-DEP": {"respuesta": "x", "responsable": "P", "fecha": "2026-01-01"}
        for n in range(1, 13)
    }
    assert not [q for q in preguntas_pendientes(control2, ruta)
                if q["id"] == "SUG-RNF"]


# ── §2.8 gestión de cambios ────────────────────────────────────────────

def test_gestion_de_cambios_sube_version_y_registra_impacto():
    control = _control_vacio()
    for q in preguntas_pendientes(control, spec_num=1):
        registrar_respuesta(control, q["id"], "ok", "Profe")
    docs = construir_specs(None, control=control)
    ok, msg = aprobar(control, 1, "Profe", markdown=docs[0].markdown)
    assert ok and "APROBADA v1.0" in msg

    docs = construir_specs(None, control=control)
    assert detectar_cambios(control, docs) == []        # sin cambios, no hace nada

    # simulo que el contenido aprobado ya no coincide con el actual
    control["estados"]["001"]["hashes"]["1"] = "hash-viejo"
    msgs = detectar_cambios(control, docs)
    assert msgs and "v1.1" in msgs[0]
    est = control["estados"]["001"]
    assert est["estado"] == "borrador" and est["version"] == "1.1"
    ev = control["eventos"][-1]
    assert ev["evento"] == "Cambio detectado" and "§1" in ev["impacto"]

    docs = construir_specs(None, control=control)
    assert "Borrador v1.1" in docs[0].markdown
    assert "re-aprobación" in docs[0].markdown

    # re-aprobar conserva la versión 1.1 y vuelve a quedar estable
    ok, msg = aprobar(control, 1, "Profe", markdown=docs[0].markdown)
    assert ok and "APROBADA v1.1" in msg
    assert control["estados"]["001"]["version"] == "1.1"
    assert detectar_cambios(control, construir_specs(None, control=control)) == []


# ── contexto del LLM construido desde el alcance ───────────────────────

def test_contexto_para_el_llm_sale_del_alcance():
    control = _control_vacio()
    ctx = contexto_proyecto(control=control)
    assert "[PROBLEMA]" in ctx and "[SOLUCIÓN]" in ctx
    assert "[OBJETIVOS]" in ctx and "movilidad de los pasajeros" in ctx
    assert "[PÚBLICO OBJETIVO]" in ctx and "Estudiantes" in ctx
    assert "[ALCANCES" in ctx and "Consulta de rutas" in ctx
    assert "FUERA DE ALCANCE" in ctx and "Pago de pasajes" in ctx
    assert "REGLAS DE NEGOCIO" in ctx and "BR-01" in ctx
    assert "[PRIORIZACIÓN]" in ctx and "Imprescindible" in ctx
    assert "[ROLES]" in ctx and "Administrador" in ctx
    # §14 RNF: los valores decididos entran; los [por definir] NO (no inventar)
    assert "REQUISITOS NO FUNCIONALES" in ctx and "| RNF-04 |" in ctx
    assert "| RNF-01 |" not in ctx and "[por definir]" not in ctx
    # las decisiones pendientes (§10) NO se filtran al modelo: no debe inventar
    assert "OPEN-Q-" not in ctx
    assert "DECISIONES YA TOMADAS" not in ctx
    assert len(ctx) < 8000                        # cabe holgadamente en num_ctx=8192

    registrar_respuesta(control, "OPEN-Q-001", "Sí, también festivos", "Profe")
    ctx2 = contexto_proyecto(control=control)
    assert "DECISIONES YA TOMADAS" in ctx2
    assert "Sí, también festivos" in ctx2

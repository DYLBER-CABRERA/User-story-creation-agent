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
    guardar_propuestas_rnf,
    preguntas_generadas,
    preguntas_pendientes,
    registrar_respuesta,
    seleccionar,
    spec_de_historia,
)
from tests.test_generar import historias_ok

VACIO = {"respuestas": {}, "estados": {}, "eventos": []}


def test_mapeo_historia_a_spec():
    # MAPEO pasajero: (1,1,2,2,3,3,4,5,5,8,9,10)
    assert spec_de_historia("pasajero", 0) == 1    # "Visualizar rutas en mapa" -> SPEC 1
    assert spec_de_historia("pasajero", 1) == 1    # "Ver recorrido en mapa" -> SPEC 1
    assert spec_de_historia("pasajero", 2) == 2    # "Consultar horarios" -> SPEC 2
    assert spec_de_historia("pasajero", 3) == 2    # "Ver frecuencia" -> SPEC 2
    assert spec_de_historia("pasajero", 4) == 3    # "GPS" -> SPEC 3
    assert spec_de_historia("pasajero", 7) == 5    # "Buscar por numero" -> SPEC 5
    assert spec_de_historia("pasajero", 9) == 8    # "Favoritas" -> SPEC 8
    assert spec_de_historia("pasajero", 11) == 10  # "Sin cuenta" -> SPEC 10
    # variante (indice >= 12) usa modulo: 12%12=0 -> 1
    assert spec_de_historia("pasajero", 12) == 1
    # MAPEO jefe_operaciones: (6,6,6,6,11,12)
    assert spec_de_historia("jefe_operaciones", 0) == 6
    assert spec_de_historia("jefe_operaciones", 3) == 6
    assert spec_de_historia("jefe_operaciones", 4) == 11
    assert spec_de_historia("jefe_operaciones", 5) == 12
    # MAPEO secretaria_movilidad: todo -> 7
    assert spec_de_historia("secretaria_movilidad", 0) == 7
    assert spec_de_historia("secretaria_movilidad", 4) == 7
    # MAPEO administrador: todo -> 13
    assert spec_de_historia("administrador", 0) == 13
    assert spec_de_historia("administrador", 4) == 13


def test_son_13_specs_y_cada_una_tiene_las_17_secciones():
    docs = construir_specs(None, control=VACIO)
    assert len(docs) == 13 == len(CATALOGO)
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
    # §6: 3 RNF medibles por SPEC con las cifras sin propuesta todavía (guía §8) +
    # las filas fijas del alcance (seguridad, integridad, compatibilidad)
    assert "| RNF-001-01 |" in d.markdown and "[por definir]" in d.markdown
    assert "SUG-001-RNF-01" in d.markdown          # cifra sin propuesta, citada en §6
    assert "| RNF-01 |" in d.markdown
    assert "sin propuesta aún" in d.markdown       # aviso: genere historias para proponer


def test_reglas_y_fuera_de_alcance_vienen_del_documento():
    docs = construir_specs(None, control=VACIO)
    # SPEC-006 ahora es el modulo del jefe de operaciones
    spec6 = next(d for d in docs if d.num == 6)
    assert "BR-03" in spec6.markdown   # jefe de operaciones - SPEC-006 usa BR-03
    assert "jefe de operaciones" in spec6.markdown.lower()
    spec1 = next(d for d in docs if d.num == 1)
    assert "Pago de pasajes" in spec1.markdown          # §14 fuera de alcance
    assert "etapa de arquitectura" in spec1.markdown   # §13 restricciones


def test_seleccionar_por_numero_o_slug():
    docs = construir_specs(None, control=VACIO)
    assert len(seleccionar(docs, "all")) == 13
    assert [d.num for d in seleccionar(docs, "003")] == [3]
    assert [d.num for d in seleccionar(docs, "3")] == [3]
    assert [d.num for d in seleccionar(docs, "rutas")] == [1]
    assert [d.num for d in seleccionar(docs, "013")] == [13]
    assert seleccionar(docs, "no-existe") == []


def test_escribir_specs_en_carpeta(tmp_path):
    docs = construir_specs(None, control=VACIO)
    rutas = escribir_specs(docs, tmp_path)
    assert len(rutas) == 13
    assert (tmp_path / "SPEC-001-consulta-de-rutas.md").exists()
    assert (tmp_path / "SPEC-012-estadisticas-basicas.md").exists()
    assert (tmp_path / "SPEC-013-modulo-administrador.md").exists()
    contenido = (tmp_path / "SPEC-001-consulta-de-rutas.md").read_text(encoding="utf-8")
    assert "## 17. Historial de cambios" in contenido


# ── control humano (guía §11-§12) ──────────────────────────────────────

def _control_vacio():
    return {"respuestas": {}, "estados": {}, "eventos": []}


def test_respuestas_se_reflejan_en_seccion_15():
    control = _control_vacio()
    pend = preguntas_pendientes(control)
    assert len(pend) >= 1                      # OPEN-Q-001 en el nuevo documento
    assert registrar_respuesta(control, "OPEN-Q-001", "Se cargan manualmente", "Profesor")
    assert not registrar_respuesta(control, "OPEN-Q-999", "no existe")
    docs = construir_specs(None, control=control)
    d = docs[0]
    assert "OPEN-Q-001** — **Respondida** (Profesor" in d.markdown
    assert "Se cargan manualmente" in d.markdown


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
    ids = {q["id"] for q in pend}
    # los RNF ya NO son preguntas: los propone el modelo en la corrida de historias
    assert {"SUG-001-CASOS", "SUG-001-DEP"} <= ids
    assert not [q for q in pend if q["id"].startswith("SUG-001-RNF-")]
    assert "SUG-RNF" not in ids
    assert not [q for q in pend if q.get("campo") == "numero"]

    docs = construir_specs(None, control=control)
    md = docs[0].markdown
    assert "Preguntas sugeridas por el agente" in md and "SUG-001-CASOS" in md
    assert "SUG-001-CASOS" not in docs[4].markdown   # las sugerencias son por SPEC

    for q in pend:
        assert registrar_respuesta(control, q["id"], f"ok: {q['id']}", "Profe")
    assert not [q for q in preguntas_pendientes(control, spec_num=1)
                if str(q["id"]).startswith("SUG-")]
    assert not registrar_respuesta(control, "SUG-XXX", "id inexistente")
    # los RNF siguen siendo corregibles por el equipo (id válido aunque no sean pregunta)
    assert registrar_respuesta(control, "SUG-001-RNF-01", "1.5", "Profe")


def test_propuestas_rnf_del_llm_se_guardan_sin_pisar_respuestas(tmp_path):
    from generador.schemas import RnfEspec

    ruta = tmp_path / "control.json"
    # el equipo ya definió la disponibilidad a mano antes de la corrida
    control = cargar_control(ruta)
    control["respuestas"]["SUG-001-RNF-02"] = {
        "respuesta": "98", "responsable": "Profe", "fecha": "2026-01-01"}
    guardar_control(control, ruta)

    rnfs = [RnfEspec(num=1, rendimiento_s=1.5, disponibilidad_pct=99.9,
                     actualizacion_min=30)]
    # solo las 2 cifras sin respuesta se guardan como propuesta del modelo
    assert guardar_propuestas_rnf(rnfs, path=ruta) == 2
    control = cargar_control(ruta)
    r = control["respuestas"]["SUG-001-RNF-01"]
    assert r["respuesta"] == "1.5"
    assert r["responsable"] == "Modelo LLM (propuesta)"
    # la respuesta humana previa no se pisa
    assert control["respuestas"]["SUG-001-RNF-02"]["respuesta"] == "98"
    # segunda corrida: ya no hay nada que proponer
    assert guardar_propuestas_rnf(rnfs, path=ruta) == 0
    # sin propuestas, no escribe nada en disco
    assert guardar_propuestas_rnf([], path=ruta) == 0

    # §6 muestra las cifras con la etiqueta de quién las definió
    md = construir_specs(None, control=cargar_control(ruta))[0].markdown
    sec6 = md.split("## 6.")[1].split("## 7.")[0]
    assert "**1.5 s** (Modelo LLM (propuesta)" in sec6
    assert "**98 %** (Profe" in sec6
    assert "[por definir]" not in sec6
    assert "sin propuesta aún" not in sec6


def test_la_nota_de_s6_cambia_cuando_se_aprueba():
    control = _control_vacio()
    sec6 = construir_specs(None, control=control)[0].markdown
    sec6 = sec6.split("## 6.")[1].split("## 7.")[0]
    assert "Los propone el modelo LLM" in sec6          # borrador: explica propuestas
    assert "confirmados por el equipo" not in sec6

    for q in preguntas_pendientes(control, spec_num=1):
        registrar_respuesta(control, q["id"], "x", "Profe")
    ok, _ = aprobar(control, 1, "Profe")
    assert ok
    sec6 = construir_specs(None, control=control)[0].markdown
    sec6 = sec6.split("## 6.")[1].split("## 7.")[0]
    assert "confirmados por el equipo al aprobar" in sec6
    assert "Los propone el modelo LLM" not in sec6      # ya no cuelga el estado viejo


def test_respuestas_de_sugerencias_alimentan_las_secciones():
    control = _control_vacio()
    for suf, val in (("01", "2"), ("02", "99.5"), ("03", "30")):
        assert registrar_respuesta(control, f"SUG-001-RNF-{suf}", val, "Profe")
    md = construir_specs(None, control=control)[0].markdown
    sec6 = md.split("## 6.")[1].split("## 7.")[0]
    assert "| RNF-001-01 |" in sec6                # fila generada por SPEC
    assert "tarda como máximo 2 segundos" in sec6 # la cifra entra al requisito
    assert "al menos el 99.5%" in sec6
    assert "cada 30 segundos" in sec6
    assert "**2 s** (Profe" in sec6                # crédito de quién definió
    assert "[por definir]" not in sec6             # las 3 respondidas + fijas "Definido"
    # los RNF respondidos ya no se listan en §15 (dejaron de ser preguntas)
    assert "SUG-001-RNF-01** — **" not in md


def test_los_rnf_no_son_preguntas_y_no_bloquean_la_aprobacion():
    control = _control_vacio()
    pend = preguntas_pendientes(control, spec_num=1)
    # ni ni global ni por SPEC hay campos numéricos ni SUG-RNF (antes: 36 + 1)
    assert not [q for q in pend if q.get("campo") == "numero"]
    assert not [q for q in pend if "RNF" in q["id"]]
    control2 = _control_vacio()
    assert not [q for q in preguntas_pendientes(control2) if q.get("campo") == "numero"]
    assert not [q for q in preguntas_pendientes(control2) if q["id"] == "SUG-RNF"]
    # aprobar solo exige resolver CASOS/DEP/OPEN-Q: las cifras RNF no bloquean
    for q in pend:
        assert registrar_respuesta(control, q["id"], "x", "Profe")
    ok, _ = aprobar(control, 1, "Profe")
    assert ok


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
    # §4 del nuevo documento = Roles (ya no hay "Público objetivo")
    assert "[ROLES]" in ctx and "Administrador" in ctx
    assert "[ALCANCES" in ctx and "Consulta de rutas" in ctx
    assert "FUERA DE ALCANCE" in ctx and "Pago de pasajes" in ctx
    assert "REGLAS DE NEGOCIO" in ctx and "BR-01" in ctx
    assert "[PRIORIZACIÓN]" in ctx and "Imprescindible" in ctx
    # RNF: solo las filas fijas decididas entran al contexto (las pendientes no)
    assert "REQUISITOS NO FUNCIONALES" in ctx and "| RNF-01 |" in ctx
    assert "[por definir]" not in ctx
    # la tabla de preguntas abiertas (con Estado/Responsable) NO se incluye en el contexto
    # (puede haber referencias OPEN-Q en el texto del documento, pero no la tabla de estado)
    assert "| Pendiente |" not in ctx     # fila de la tabla de preguntas no debe aparecer
    assert "DECISIONES YA TOMADAS" not in ctx

    registrar_respuesta(control, "OPEN-Q-001", "Sí, también festivos", "Profe")
    ctx2 = contexto_proyecto(control=control)
    assert "DECISIONES YA TOMADAS" in ctx2
    assert "Sí, también festivos" in ctx2

    # una propuesta del modelo va en bloque aparte, no como decisión del equipo
    registrar_respuesta(control, "SUG-002-RNF-01", "1.5", "Modelo LLM (propuesta)")
    ctx3 = contexto_proyecto(control=control)
    i_dec = ctx3.find("DECISIONES")
    i_prop = ctx3.find("RNF PROPUESTOS POR EL MODELO")
    i_rnf = ctx3.find("SUG-002-RNF-01")
    assert 0 <= i_dec < i_prop < i_rnf
    assert "pendiente de aprobación" in ctx3

from generador.specs import (
    CATALOGO,
    construir_specs,
    escribir_specs,
    seleccionar,
    spec_de_historia,
)
from tests.test_generar import historias_ok


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
    docs = construir_specs(None)
    assert len(docs) == 12 == len(CATALOGO)
    for d in docs:
        for n in range(1, 18):
            assert f"## {n}." in d.markdown, f"{d.titulo} sin sección {n}"
        assert "pendiente de aprobación humana" in d.markdown


def test_spec_con_historias_incluye_rf_flujos_ac_y_trazabilidad():
    docs = construir_specs(historias_ok())
    spec1 = next(d for d in docs if d.num == 1)   # HU-P01 y HU-P02 caen en 001
    assert "RF-001-01" in spec1.markdown and "HU-P01" in spec1.markdown
    assert "RF-001-02" in spec1.markdown and "HU-P02" in spec1.markdown
    assert "AC-001-01" in spec1.markdown
    assert "Dado" in spec1.markdown                 # criterios Dado/Cuando/Entonces
    assert "Flujo" in spec1.markdown
    assert "| HU-P01 | RF-001-01" in spec1.markdown  # tabla §16
    # SPEC sin historias en esta corrida -> pendiente
    spec8 = next(d for d in docs if d.num == 8)
    assert "Pendiente" in spec8.markdown


def test_spec_sin_historias_marca_pendientes():
    docs = construir_specs(None)
    d = docs[0]
    assert "sin historias asignadas" in d.markdown
    assert "> **Pendiente:** los requisitos no funcionales" in d.markdown


def test_reglas_y_fuera_de_alcance_vienen_del_documento():
    docs = construir_specs(None)
    spec6 = next(d for d in docs if d.num == 6)
    assert "BR-03" in spec6.markdown
    assert "Solo el administrador crea" in spec6.markdown        # §7 alcance
    spec1 = next(d for d in docs if d.num == 1)
    assert "Pago de pasajes" in spec1.markdown                     # §6 alcance en §14
    assert "8 semanas" in spec1.markdown                         # §12 alcance en §13


def test_seleccionar_por_numero_o_slug():
    docs = construir_specs(None)
    assert len(seleccionar(docs, "all")) == 12
    assert [d.num for d in seleccionar(docs, "003")] == [3]
    assert [d.num for d in seleccionar(docs, "3")] == [3]
    assert [d.num for d in seleccionar(docs, "rutas")] == [1]
    assert seleccionar(docs, "no-existe") == []


def test_escribir_specs_en_carpeta(tmp_path):
    docs = construir_specs(None)
    rutas = escribir_specs(docs, tmp_path)
    assert len(rutas) == 12
    assert (tmp_path / "SPEC-001-consulta-de-rutas.md").exists()
    assert (tmp_path / "SPEC-012-estadisticas-basicas.md").exists()
    contenido = (tmp_path / "SPEC-001-consulta-de-rutas.md").read_text(encoding="utf-8")
    assert "## 17. Historial de cambios" in contenido

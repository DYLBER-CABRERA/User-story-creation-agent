"""Generación de SPECs (especificaciones) por funcionalidad.

Ensambla el documento de las 17 secciones de la guía del Specification Agent
(docs/Guia - Specification Agent.md, sección 7) a partir de:

- docs/alcance-contexto-proyecto.md -> contexto, alcance, reglas, restricciones,
  fuera de alcance y preguntas abiertas (fuente única de verdad).
- las historias ya generadas        -> RF (§5), flujos (§8-9), criterios (§11)
  y trazabilidad (§16).

Regla de la guía (§11): NO se inventa contenido. Lo que no esté definido se marca
explícitamente como "Pendiente" con su responsable.

Asignación historia -> SPEC: por posición dentro de cada rol (el prompt exige el
orden de temas de temas.py); con módulo len(temas_base) cubre las variantes.

Uso:
    from generador.specs import construir_specs, escribir_specs
    docs = construir_specs(historias)          # historias=None -> esqueletos pendientes
    escribir_specs(docs)                       # escribe docs/specs/SPEC-XXX-slug.md

CLI:
    python -m generador.specs                          # esqueleto desde el alcance
    python -m generador.specs --historias hist.json    # SPECs completas
"""
from __future__ import annotations

import argparse
import datetime
import re
from dataclasses import dataclass
from pathlib import Path

from .schemas import HistoriasGeneradas
from .temas import TEMAS_POR_ROL

RAIZ = Path(__file__).resolve().parent.parent
ALCANCE_PATH = RAIZ / "docs" / "alcance-contexto-proyecto.md"
SPECS_DIR = RAIZ / "docs" / "specs"


@dataclass(frozen=True)
class Funcionalidad:
    num: int
    slug: str
    nombre: str
    actores: tuple[str, ...]
    objetivo: str
    clave_alcance: str   # nombre del bullet en §5 del documento de alcance
    brs: tuple[str, ...]  # reglas de negocio aplicables (§7 del alcance)


CATALOGO: tuple[Funcionalidad, ...] = (
    Funcionalidad(1, "consulta-de-rutas", "Consulta de rutas", ("Pasajero",),
                  "Permitir al pasajero consultar el catálogo de rutas de buseta de Manizales con su recorrido en el mapa.",
                  "Consulta de rutas", ("BR-01",)),
    Funcionalidad(2, "consulta-de-horarios", "Consulta de horarios", ("Pasajero",),
                  "Informar los horarios, frecuencia y días de operación de cada ruta.",
                  "Consulta de horarios", ("BR-01",)),
    Funcionalidad(3, "seguimiento-gps-eta", "Seguimiento en tiempo real (GPS/ETA)", ("Pasajero",),
                  "Mostrar la ubicación en tiempo real de las busetas y el tiempo estimado de llegada (ETA) a una parada.",
                  "Seguimiento en tiempo real", ("BR-01",)),
    Funcionalidad(4, "planificacion-de-viaje", "Planificación de viaje", ("Pasajero",),
                  "Ayudar al pasajero a planificar un viaje indicando origen y destino.",
                  "Planificación de viaje", ("BR-01",)),
    Funcionalidad(5, "busqueda-y-filtros", "Búsqueda y filtros", ("Pasajero",),
                  "Permitir buscar rutas por número, nombre, barrio o punto de interés.",
                  "Búsqueda y filtros", ("BR-01",)),
    Funcionalidad(6, "modulo-administrativo", "Módulo administrativo", ("Administrador",),
                  "Permitir al administrador crear y actualizar rutas, horarios, paradas y busetas.",
                  "Módulo administrativo", ("BR-03",)),
    Funcionalidad(7, "modulo-de-conductores", "Módulo de conductores", ("Conductor",),
                  "Permitir al conductor consultar su ruta asignada, iniciar/finalizar el recorrido y reportar la posición de la buseta.",
                  "Módulo de conductores", ("BR-05",)),
    Funcionalidad(8, "favoritas", "Favoritas", ("Pasajero",),
                  "Permitir al pasajero guardar rutas o paradas frecuentes para encontrarlas rápido.",
                  "Favoritas", ("BR-02",)),
    Funcionalidad(9, "notificaciones", "Notificaciones", ("Pasajero",),
                  "Avisar al pasajero cuando la buseta esté por llegar a una parada que le interesa.",
                  "Notificaciones", ("BR-02",)),
    Funcionalidad(10, "uso-sin-cuenta", "Uso sin cuenta", ("Pasajero",),
                  "Permitir consultar la app sin obligar a crear una cuenta.",
                  "Uso sin cuenta", ("BR-01", "BR-02")),
    Funcionalidad(11, "avisos-generales", "Avisos generales", ("Administrador",),
                  "Permitir al administrador publicar avisos generales (cambios, suspensiones, festivos).",
                  "Avisos generales", ("BR-04",)),
    Funcionalidad(12, "estadisticas-basicas", "Estadísticas básicas", ("Administrador",),
                  "Mostrar al administrador estadísticas básicas de uso de la app.",
                  "Estadísticas básicas", ("BR-03",)),
)

# Índice de tema base -> número de SPEC, por rol (alineado con temas.py).
# El índice de la historia se toma con módulo para cubrir las variantes.
MAPEO_POR_ROL: dict[str, tuple[int, ...]] = {
    "pasajero": (1, 1, 2, 3, 3, 4, 5, 8, 9, 10),
    "conductor": (7, 7, 7, 7, 7),
    "administrador": (6, 6, 6, 11, 12),
}


def spec_de_historia(rol: str, indice: int) -> int:
    """Número de SPEC (1-12) que recibe la historia `indice`-ésima del rol."""
    base = MAPEO_POR_ROL[rol]
    return base[indice % len(base)]


@dataclass(frozen=True)
class SpecDoc:
    num: int
    slug: str
    nombre: str
    markdown: str

    @property
    def titulo(self) -> str:
        return f"SPEC-{self.num:03d} — {self.nombre}"

    @property
    def nombre_archivo(self) -> str:
        return f"SPEC-{self.num:03d}-{self.slug}.md"


# ───────────────────── lectura del documento de alcance ─────────────────────

def _leer_alcance(path: Path = ALCANCE_PATH) -> dict[str, str]:
    """{'1. Descripción del problema': cuerpo, ...} por cada encabezado '## N.'."""
    if not path.exists():
        return {}
    secciones: dict[str, list[str]] = {}
    actual: str | None = None
    for linea in path.read_text(encoding="utf-8").splitlines():
        if linea.startswith("## "):
            actual = linea[3:].strip()
            secciones[actual] = []
        elif actual is not None:
            secciones[actual].append(linea)
    return {k: "\n".join(v).strip() for k, v in secciones.items()}


def _sec(secciones: dict[str, str], num: int) -> str:
    for titulo, cuerpo in secciones.items():
        if titulo.startswith(f"{num}."):
            return cuerpo
    return "_Ver docs/alcance-contexto-proyecto.md._"


def _bullet(texto: str, clave: str) -> str | None:
    """Extrae '* **Clave:** valor...' (con sus líneas de continuación)."""
    lineas = (texto or "").splitlines()
    prefijo = f"* **{clave}:**"
    for i, ln in enumerate(lineas):
        if ln.startswith(prefijo):
            trozos = [ln[len(prefijo):]]
            for cont in lineas[i + 1:]:
                if not cont.strip() or cont.lstrip().startswith(("* ", "## ")):
                    break
                trozos.append(cont.strip())
            return " ".join(" ".join(trozos).split())
    return None


def _reglas(texto: str) -> dict[str, str]:
    """{'BR-01': 'texto...', ...} desde los bullets de §7."""
    regs: dict[str, str] = {}
    lineas = (texto or "").splitlines()
    i = 0
    while i < len(lineas):
        m = re.match(r"\* \*\*(BR-\d+):\*\*\s*(.*)", lineas[i])
        if m:
            clave, txt = m.group(1), [m.group(2)]
            j = i + 1
            while j < len(lineas) and lineas[j].strip() and not lineas[j].startswith(("* ", "## ")):
                txt.append(lineas[j].strip())
                j += 1
            regs[clave] = " ".join(" ".join(txt).split())
            i = j
        else:
            i += 1
    return regs


# ───────────────────────── ensamblado de la SPEC ─────────────────────────

def _tema_de(rol: str, indice: int) -> str:
    base = TEMAS_POR_ROL[rol]
    return base[indice % len(base)]


def _construir_markdown(
    func: Funcionalidad,
    asignadas: list[tuple[str, int, object]],  # (rol, indice, historia)
    secciones: dict[str, str],
) -> str:
    fecha = datetime.date.today().isoformat()
    reglas = _reglas(_sec(secciones, 7))
    n = func.num
    actores = ", ".join(func.actores)

    cabecera = (
        f"# SPEC-{n:03d} — {func.nombre}\n\n"
        "| Campo | Valor |\n|-------|-------|\n"
        f"| Versión | 1.0 |\n"
        f"| Estado | Borrador — pendiente de aprobación humana |\n"
        f"| Funcionalidad | {func.nombre} |\n"
        f"| Actores | {actores} |\n"
        f"| Generado | {fecha} (automático) |\n\n"
        "> Fuente: `docs/alcance-contexto-proyecto.md` + historias de usuario generadas.\n"
        "> Estructura según la sección 7 de la guía del Specification Agent.\n"
    )

    # §5 Requisitos funcionales (de las historias)
    rf_lineas: list[str] = []
    ac_lineas: list[str] = []
    flujo_norm: list[str] = []
    flujo_alt: list[str] = []
    limite: list[str] = []
    traza: list[str] = []
    ac_seq = 0
    for rf_seq, (rol, indice, h) in enumerate(asignadas, start=1):
        rf_id = f"RF-{n:03d}-{rf_seq:02d}"
        rf_lineas.append(f"- **{rf_id}** [{h.id}] Como {h.como}, quiero {h.quiero}, para {h.para}.")
        flujo_norm.append(f"- **{h.id}:** {' → '.join(h.flujo_normal)}")
        flujo_alt.append(f"- **{h.id}:** {' → '.join(h.flujo_alternativo)}")
        limite.extend(f"- **{h.id}:** {paso}" for paso in h.flujo_alternativo)
        ac_ids = []
        for j, c in enumerate(h.criterios, start=1):
            ac_seq += 1
            ac_id = f"AC-{n:03d}-{ac_seq:02d}"
            ac_ids.append(ac_id)
            ac_lineas.append(f"- **{ac_id}** [{h.id}.CA-{j}] {c.texto}")
        traza.append(f"| {h.id} | {rf_id} | {', '.join(ac_ids)} | {_tema_de(rol, indice)} |")

    if not asignadas:
        pendiente_hist = "> **Pendiente:** sin historias asignadas en la corrida actual. Genere historias (app o CLI) y vuelva a exportar."
        rf_lineas = [pendiente_hist]
        ac_lineas = [pendiente_hist]
        flujo_norm = [pendiente_hist]
        flujo_alt = [pendiente_hist]
        limite = [pendiente_hist]
        traza = []

    traza_md = (
        "| Historia | Requisito | Criterios | Tema |\n|----------|-----------|-----------|------|\n"
        + "\n".join(traza)
        if traza
        else "> **Pendiente:** sin historias para trazar."
    )

    br_md = "\n".join(
        f"- **{clave}:** {reglas[clave]}" if clave in reglas else f"- **{clave}:** _Ver §7 del documento de alcance._"
        for clave in func.brs
    )
    alcance_func = _bullet(_sec(secciones, 5), func.clave_alcance)

    return f"""{cabecera}
## 1. Objetivo
{func.objetivo}

## 2. Contexto
{_sec(secciones, 1)}

{_sec(secciones, 2)}

## 3. Alcance
{f"- {alcance_func}" if alcance_func else "_Ver §5 de docs/alcance-contexto-proyecto.md._"}

Ver también **Fuera de alcance** (§14 de esta SPEC).

## 4. Actores
{chr(10).join(f'- **{a}**' for a in func.actores)}

## 5. Requisitos funcionales
{chr(10).join(rf_lineas)}

## 6. Requisitos no funcionales
> **Pendiente:** los requisitos no funcionales (rendimiento, disponibilidad, seguridad...)
> aún no están definidos en el documento de alcance. Responsable: Equipo.

## 7. Reglas de negocio
{br_md}

## 8. Flujos principales
{chr(10).join(flujo_norm)}

## 9. Flujos alternativos
{chr(10).join(flujo_alt)}

## 10. Casos límite
{chr(10).join(limite)}
- Casos límite adicionales (concurrencia, valores extremos): **pendiente de análisis** (guía §2.6).

## 11. Criterios de aceptación
{chr(10).join(ac_lineas)}

## 12. Dependencias
> **Pendiente:** corresponde a la etapa de arquitectura, no definida en este documento.

## 13. Restricciones
{_sec(secciones, 12)}

## 14. Fuera de alcance
{_sec(secciones, 6)}

## 15. Preguntas abiertas
{_sec(secciones, 10)}

## 16. Trazabilidad
{traza_md}

## 17. Historial de cambios
| Versión | Fecha | Cambio | Aprobación |
|---------|-------|--------|------------|
| 1.0 | {fecha} | Generación automática desde alcance + historias | Pendiente (humana) |
"""


def construir_specs(
    historias: HistoriasGeneradas | None = None,
    alcance_path: Path = ALCANCE_PATH,
) -> list[SpecDoc]:
    """Arma las 12 SPECs. `historias=None` genera esqueletos con §8/§9/§11/§16 pendientes."""
    secciones = _leer_alcance(alcance_path)

    asignadas: dict[int, list[tuple[str, int, object]]] = {f.num: [] for f in CATALOGO}
    if historias is not None:
        for rol, lista in (
            ("pasajero", historias.pasajero),
            ("conductor", historias.conductor),
            ("administrador", historias.administrador),
        ):
            for i, h in enumerate(lista):
                asignadas[spec_de_historia(rol, i)].append((rol, i, h))

    docs: list[SpecDoc] = []
    for func in CATALOGO:
        docs.append(
            SpecDoc(
                num=func.num,
                slug=func.slug,
                nombre=func.nombre,
                markdown=_construir_markdown(func, asignadas[func.num], secciones),
            )
        )
    return docs


def escribir_specs(docs: list[SpecDoc], carpeta: Path | str = SPECS_DIR) -> list[Path]:
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = []
    for d in docs:
        ruta = carpeta / d.nombre_archivo
        ruta.write_text(d.markdown, encoding="utf-8")
        rutas.append(ruta)
    return rutas


def seleccionar(docs: list[SpecDoc], valor: str) -> list[SpecDoc]:
    """Filtra por 'all', número (3, 003), slug (rutas) o nombre (substring)."""
    v = valor.strip().lower().replace(" ", "-")
    if v in ("all", "*", ""):
        return docs
    elegidos = [
        d for d in docs
        if v in (d.slug, str(d.num), f"{d.num:03d}", f"spec-{d.num:03d}", d.nombre.lower().replace(" ", "-"))
        or v in d.slug
        or v in d.nombre.lower()
    ]
    return elegidos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Genera las 12 SPECs (17 secciones, guía §7) desde el documento de alcance."
    )
    ap.add_argument("--historias", help="JSON de historias exportado con CLI --json (opcional)")
    ap.add_argument("--spec", default="all", help="Todas (default) o un número/slug (ej. 003, rutas)")
    ap.add_argument("--out", default=str(SPECS_DIR), help="Carpeta de salida (default: docs/specs)")
    args = ap.parse_args(argv)

    historias: HistoriasGeneradas | None = None
    if args.historias:
        texto = Path(args.historias).read_text(encoding="utf-8")
        historias = HistoriasGeneradas.model_validate_json(texto)

    docs = seleccionar(construir_specs(historias), args.spec)
    if not docs:
        print(f"Ninguna SPEC coincide con '{args.spec}'.", flush=True)
        return 1
    rutas = escribir_specs(docs, args.out)
    for r in rutas:
        print(r, flush=True)
    print(f"{len(rutas)} SPEC(s) escritas en {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

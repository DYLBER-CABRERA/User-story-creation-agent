"""Interfaz Streamlit del generador de historias de usuario. Ejecutar: streamlit run app.py"""
from __future__ import annotations

import io
import zipfile

import pandas as pd
import streamlit as st

from generador.config import get_settings
from generador.generar import APP_NAME_DEFAULT, CONTEXT_DEFAULT, build_chain, generar_historias
from generador.temas import TEMAS_POR_ROL
from generador.llm import build_providers
from generador.schemas import HistoriasGeneradas
from generador.specs import (
    aprobar,
    cargar_control,
    construir_specs,
    congelar,
    contexto_proyecto,
    detectar_cambios,
    escribir_specs,
    guardar_control,
    preguntas_pendientes,
    registrar_respuesta,
)

st.set_page_config(page_title="Generador de Historias de Usuario", page_icon="🚌", layout="wide")

SETTINGS = get_settings()
OPCIONES = ("ollama", "gemini", "groq")
PROVIDER_LABELS = {
    "ollama": "🟢 Ollama (local)",
    "gemini": "✨ Gemini (API)",
    "groq": "⚡ Groq (API)",
}


def orden_de(proveedor: str) -> tuple[str, ...]:
    """El elegido primero; los demás quedan como respaldo en orden."""
    return (proveedor,) + tuple(p for p in OPCIONES if p != proveedor)


@st.cache_resource(show_spinner=False)
def get_chain(proveedor: str, modelo: str):
    """Cadena cacheada por (proveedor, modelo): cambiar cualquiera de los dos la reconstruye."""
    return build_chain(
        build_providers(SETTINGS, order=orden_de(proveedor), modelos={proveedor: modelo}),
        sin_fallbacks=True,
    )


def to_dataframe(historias: HistoriasGeneradas) -> pd.DataFrame:
    filas = [
        {
            "ID": h.id, "Rol": h.rol, "Como": h.como, "Quiero": h.quiero, "Para": h.para,
            "Flujo normal": " → ".join(h.flujo_normal),
            "Flujo alternativo": " → ".join(h.flujo_alternativo),
            "Flujo excepción": " → ".join(h.flujo_excepcion),
            "Criterios de aceptación": " | ".join(c.texto for c in h.criterios),
        }
        for h in historias.todas()
    ]
    return pd.DataFrame(filas)


def to_texto(historias: HistoriasGeneradas) -> str:
    partes = []
    for titulo, lista in [
        ("PASAJERO", historias.pasajero),
        ("JEFE DE OPERACIONES", historias.jefe_operaciones),
        ("SECRETARÍA DE MOVILIDAD", historias.secretaria_movilidad),
        ("ADMINISTRADOR", historias.administrador),
    ]:
        if lista:
            partes.append(f"## {titulo}")
            partes.extend(h.detalle for h in lista)
    return "\n".join(partes)


# ───────────────────────── barra lateral ─────────────────────────
with st.sidebar:
    st.header("⚙️ Configuración")

    st.subheader("Proveedor")
    proveedor = st.radio(
        "Conectar con",
        options=list(OPCIONES),
        format_func=lambda p: PROVIDER_LABELS[p],
        horizontal=True,
        index=(
            OPCIONES.index(SETTINGS.provider_order[0])
            if SETTINGS.provider_order and SETTINGS.provider_order[0] in OPCIONES
            else 0
        ),
    )
    modelo_default = {
        "ollama": SETTINGS.ollama_model,
        "gemini": SETTINGS.gemini_model,
        "groq": SETTINGS.groq_model,
    }[proveedor]
    modelo = st.text_input(
        "Modelo",
        value=modelo_default,
        key=f"modelo_{proveedor}",
        help="Modelo a usar en el proveedor elegido. El otro proveedor queda como respaldo con su modelo del .env.",
    )

    order = orden_de(proveedor)
    try:
        proveedores = [n for n, _ in build_providers(SETTINGS, order=order, modelos={proveedor: modelo})]
    except Exception:
        proveedores = []
    if proveedores:
        primario, *respaldo = proveedores
        etiqueta = PROVIDER_LABELS.get(primario, primario)
        if respaldo:
            st.success(f"Principal: {etiqueta} · Respaldo: {', '.join(respaldo)}")
        else:
            st.success(f"Usará únicamente: {etiqueta}")
        if primario != proveedor:
            motivo = {
                "gemini": "(falta GOOGLE_API_KEY)",
                "groq": "(falta GROQ_API_KEY)",
            }.get(proveedor, "(error de configuración)")
            st.warning(
                f"{PROVIDER_LABELS[proveedor]} no está disponible "
                f"{motivo}; se usará {PROVIDER_LABELS.get(primario, primario)}."
            )
    else:
        st.error("No hay proveedores configurados. Revisa Ollama, GOOGLE_API_KEY o GROQ_API_KEY en .env")

    app_name = st.text_input("Nombre de la app", APP_NAME_DEFAULT)
    contexto = st.text_area(
        "Contexto del proyecto",
        contexto_proyecto() or CONTEXT_DEFAULT,
        height=180,
        help="Generado desde docs/contexto-busetasapp.md. Edítalo si quieres acotarlo.",
    )

    n_por_rol = {rol: len(temas) for rol, temas in TEMAS_POR_ROL.items()}
    total = sum(n_por_rol.values())
    st.caption(
        f"Historias a generar: **{total}** en total — "
        + ", ".join(f"{rol.replace('_', ' ')}: {n}" for rol, n in n_por_rol.items())
        + ". La cantidad la determina el alcance del proyecto (temas.py)."
    )
    if total > 20:
        st.caption(
            "⚠️ Con tantas historias los modelos pequeños pueden tardar varios minutos "
            "o no alcanzar el contexto; si falla, sube `OLLAMA_NUM_CTX`."
        )

    st.subheader("Depuración")
    debug_prompt = st.checkbox(
        "Imprimir prompt exacto y tiempos en la terminal",
        value=False,
        help="Al generar, imprime en la terminal donde corre `streamlit run` el prompt "
             "completo que va al LLM (contexto ya interpolado) y el tiempo de cada "
             "intento. Igual que --debug-prompt en la CLI.",
    )

# ───────────────────────── página principal ─────────────────────────
st.title("🚌 Generador de Historias de Usuario")
st.caption("LangChain · Pydantic · Ollama local, Gemini o Groq API, con respaldo automático")

if "historias" not in st.session_state:
    st.session_state.historias = None
    st.session_state.segundos = None
    st.session_state.proveedor_usado = None

if st.button("Generar historias", type="primary", disabled=not proveedores):
    primario = proveedores[0] if proveedores else proveedor
    modelo_primario = modelo if primario == proveedor else {
        "ollama": SETTINGS.ollama_model,
        "gemini": SETTINGS.gemini_model,
        "groq": SETTINGS.groq_model,
    }[primario]
    with st.spinner(f"Generando con {primario} ({modelo_primario})…"):
        try:
            chain = get_chain(proveedor, modelo)
            historias, segundos = generar_historias(
                app_name=app_name,
                context=contexto,
                chain=chain,
                debug=debug_prompt,
            )
            st.session_state.historias = historias
            st.session_state.segundos = segundos
            st.session_state.proveedor_usado = primario
        except Exception as exc:  # noqa: BLE001
            st.error(f"No se pudo generar: {exc}")

historias: HistoriasGeneradas | None = st.session_state.historias
if historias:
    usado = st.session_state.get("proveedor_usado")
    detalle_prov = f" · con {PROVIDER_LABELS.get(usado, usado)}" if usado else ""
    st.success(f"Generado en {st.session_state.segundos:.1f} s · {len(historias.todas())} historias{detalle_prov}")

    tab_pasajero, tab_jefe, tab_secretaria, tab_admin, tab_todas = st.tabs(
        [f"Pasajero ({len(historias.pasajero)})",
         f"Jefe Op. ({len(historias.jefe_operaciones)})",
         f"Secretaría ({len(historias.secretaria_movilidad)})",
         f"Administrador ({len(historias.administrador)})",
         "Todas"]
    )
    for tab, lista in [
        (tab_pasajero, historias.pasajero),
        (tab_jefe, historias.jefe_operaciones),
        (tab_secretaria, historias.secretaria_movilidad),
        (tab_admin, historias.administrador),
    ]:
        with tab:
            for h in lista:
                st.markdown(f"**{h.id}** — Como *{h.como}*, quiero {h.quiero}, para {h.para}.")
                st.markdown(
                    f"- *Flujo normal:* {' → '.join(h.flujo_normal)}\n"
                    f"- *Flujo alternativo:* {' → '.join(h.flujo_alternativo)}\n"
                    f"- *Flujo de excepción:* {' → '.join(h.flujo_excepcion)}\n"
                    + "\n".join(f"- *CA-{i}:* {c.texto}" for i, c in enumerate(h.criterios, 1))
                )

    with tab_todas:
        st.dataframe(to_dataframe(historias), hide_index=True, width="stretch")

    c1, c2 = st.columns(2)
    c1.download_button(
        "Descargar como texto (.txt)",
        to_texto(historias),
        file_name="historias_usuario.txt",
        mime="text/plain",
    )
    c2.download_button(
        "Descargar como CSV",
        # utf-8-sig: agrega BOM para que Excel muestre bien las tildes/ñ
        to_dataframe(historias).to_csv(index=False).encode("utf-8-sig"),
        file_name="historias_usuario.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("Especificaciones (SPEC)")
    control = cargar_control()
    docs = construir_specs(historias, control=control)
    cambios = detectar_cambios(control, docs)
    if cambios:
        guardar_control(control)
        docs = construir_specs(historias, control=control)
        st.warning(
            "**§2.8 Gestión de cambios** — contenido alterado en SPEC(s) aprobada(s); "
            "se subió la versión y quedan pendientes de re-aprobación:\n\n"
            + "\n".join(f"- {m}" for m in cambios)
        )
    if st.button("Exportar SPECs a docs/specs/"):
        rutas = escribir_specs(docs)
        st.success(f"{len(rutas)} SPECs escritas en docs/specs/")

    sel = st.selectbox("Previsualizar SPEC", [d.titulo for d in docs])
    doc_sel = next(d for d in docs if d.titulo == sel)

    # ── control humano (guía §12): preguntas abiertas + sugeridas por el agente ──
    pendientes = preguntas_pendientes(control, spec_num=doc_sel.num)
    with st.expander(f"Preguntas de SPEC-{doc_sel.num:03d} — {len(pendientes)} sin responder"):
        st.caption(
            "Los RNF no son preguntas: los propone el modelo al generar historias "
            "(etiquetados 'Modelo LLM (propuesta)') y se confirman al aprobar la SPEC. "
            "Aquí solo quedan casos límite, dependencias y alcance (§5 pasos 5-6): "
            "la guía §12 exige resolverlas todas antes de aprobar."
        )
        campos = []
        for q in pendientes:
            etiqueta = (
                f"{q['id']} — {q['pregunta']}"
                + ("  [sugerida]" if q.get("generada") else "")
            )
            campos.append((
                q,
                st.text_input(etiqueta, key=f"resp-{q['id']}-{len(pendientes)}"),
            ))
        if st.button("Guardar respuestas"):
            guardadas = 0
            for q, texto in campos:
                if not texto or not texto.strip():
                    continue
                if registrar_respuesta(control, q["id"], texto.strip(), "Web"):
                    guardadas += 1
            if guardadas:
                guardar_control(control)
                st.success(f"{guardadas} respuesta(s) guardada(s).")
                st.rerun()
            else:
                st.warning("Escribe al menos una respuesta.")

    # ── aprobación y congelación (guía §12) ──
    clave = f"{doc_sel.num:03d}"
    estado = (control.get("estados") or {}).get(clave, {}).get("estado", "borrador")
    quien = st.text_input("Aprobado por", value="Equipo", key="aprobado_por")
    b1, b2, b3 = st.columns([1, 1, 2])
    if b1.button("Aprobar (v1.0)", disabled=estado != "borrador" or bool(pendientes)):
        ok, msg = aprobar(control, doc_sel.num, quien.strip() or "Equipo")
        if ok:
            guardar_control(control)
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)
    if b2.button("Congelar (FROZEN)", disabled=estado != "aprobada"):
        ok, msg = congelar(control, doc_sel.num)
        if ok:
            guardar_control(control)
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)
    if estado == "borrador" and pendientes:
        b3.caption(f"Para aprobar: responde {len(pendientes)} pregunta(s) abierta(s) (guía §12).")
    else:
        b3.caption(f"Estado actual: **{estado}**")

    with st.expander(f"Ver Markdown de {doc_sel.nombre_archivo}"):
        st.code(doc_sel.markdown, language="markdown")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in docs:
            zf.writestr(d.nombre_archivo, d.markdown)
    st.download_button(
        "Descargar todas las SPECs (.zip)",
        buf.getvalue(),
        file_name="specs-busetasapp.zip",
        mime="application/zip",
    )
else:
    st.info("Ajusta las cantidades y el contexto en la barra lateral, y pulsa **Generar historias**.")

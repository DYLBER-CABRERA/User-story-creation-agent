"""Interfaz Streamlit del generador de historias de usuario. Ejecutar: streamlit run app.py.

Lógica general:
  - Cada interacción (click de botón, cambio de widget) re-ejecuta este script
    entero (modelo de rerun de Streamlit); el estado persiste en st.session_state
    y la cadena LLM se cachea con @st.cache_resource para NO reconstruirla en
    cada rerun.
"""
from __future__ import annotations  # anotaciones perezosas

# pandas: estructura DataFrame para la tabla "Todas" y el CSV descargable
import pandas as pd
# streamlit: framework de UI web en Python (cada st.* dibuja un widget)
import streamlit as st

# Imports del paquete generador (config, cadena, proveedores, esquemas)
from generador.config import get_settings
from generador.generar import APP_NAME_DEFAULT, CONTEXT_DEFAULT, build_chain, generar_historias
from generador.llm import build_providers
from generador.schemas import HistoriasGeneradas

# set_page_config: DEBE ser la PRIMERA llamada de Streamlit en el script;
# define título, favicon y layout="wide" (ancho completo, sin columna estrecha)
st.set_page_config(page_title="Generador de Historias de Usuario", page_icon="🚌", layout="wide")

# Se leen UNA vez al cargar el módulo (antes del rerun de widgets)
SETTINGS = get_settings()  # Settings del .env (modelos, orden, temperature)
# Mapa proveedor -> etiqueta bonita para mostrar en radios/labels
PROVIDER_LABELS = {"ollama": "🟢 Ollama (local)", "gemini": "✨ Gemini (API)"}


# @st.cache_resource -> cachea el OBJETO por args (clave interna = hash de args):
# solo se reconstruye la cadena si cambian (proveedor, modelo).
# show_spinner=False -> no muestra spinner (ya hay uno en el botón).
@st.cache_resource(show_spinner=False)
def get_chain(proveedor: str, modelo: str):
    """Cadena cacheada por (proveedor, modelo): cambiar cualquiera de los dos la reconstruye."""
    # Traduce la elección del usuario a orden de fallbacks (primario primero)
    order = ("ollama", "gemini") if proveedor == "ollama" else ("gemini", "ollama")
    # build_providers arma clientes; modelos={proveedor: modelo} pisa el modelo elegido;
    # build_chain envuelve prompt|structured_output|retry|fallback
    return build_chain(build_providers(SETTINGS, order=order, modelos={proveedor: modelo}))


def to_dataframe(historias: HistoriasGeneradas) -> pd.DataFrame:
    """Convierte las 3 listas en un DataFrame plano (una fila por historia).

    Comprensión de lista de dicts -> pd.DataFrame(dict_list): pandas crea las
    columnas a partir de las llaves de cada dict automáticamente.
    """
    filas = [
        # Cada fila es un dict; h.texto no se usa aquí porque se separan columnas
        {"ID": h.id, "Rol": h.rol, "Como": h.como, "Quiero": h.quiero, "Para": h.para}
        for h in historias.todas()  # todas() aplana pasajero+conductor+admin
    ]
    return pd.DataFrame(filas)


def to_texto(historias: HistoriasGeneradas) -> str:
    """Serializa a .txt con encabezados ## POR ROL (mismo formato que la CLI)."""
    partes = []  # acumulador de líneas del archivo
    # Lista de tuplas (título, lista) para no repetir el bloque 3 veces
    for titulo, lista in [
        ("PASAJERO", historias.pasajero),
        ("CONDUCTOR", historias.conductor),
        ("ADMINISTRADOR", historias.administrador),
    ]:
        if lista:  # solo agrega sección si tiene historias (evita "## VACÍO")
            partes.append(f"## {titulo}")           # encabezado
            partes.extend(h.texto for h in lista)   # una línea por historia
    return "\n".join(partes)  # une todo con saltos de línea


# ───────────────────────── barra lateral ─────────────────────────
# with st.sidebar: todos los widgets de ESTE bloque se dibujan en la columna
# izquierda en vez del área principal.
with st.sidebar:
    st.header("⚙️ Configuración")

    st.subheader("Proveedor")
    # st.radio: selector exclusivo; options = valores crudos que devuelve,
    # format_func = cómo se etiqueta cada uno en pantalla,
    # horizontal=True = en fila; index = cuál viene seleccionado al abrir.
    proveedor = st.radio(
        "Conectar con",
        options=["ollama", "gemini"],
        format_func=lambda p: PROVIDER_LABELS[p],  # lambda: función anónima de 1 línea
        horizontal=True,
        # Si el .env arranca con gemini primero, preselecciona gemini en el radio
        index=0 if SETTINGS.provider_order[:1] != ("gemini",) else 1,
    )
    # Modelo por defecto según el proveedor activo en el radio (editable por el usuario)
    modelo_default = SETTINGS.ollama_model if proveedor == "ollama" else SETTINGS.gemini_model
    # key=f"modelo_{proveedor}" -> Streamlit guarda el valor por key en
    # st.session_state; al cambiar de proveedor se usa el otro campo de texto.
    modelo = st.text_input(
        "Modelo",
        value=modelo_default,
        key=f"modelo_{proveedor}",
        help="Modelo a usar en el proveedor elegido. El otro proveedor queda como respaldo con su modelo del .env.",
    )

    # Reordena el par (primario, respaldo) según la elección del radio
    order = ("ollama", "gemini") if proveedor == "ollama" else ("gemini", "ollama")
    try:
        # Solo para MOSTRAR quién es principal/respaldo (sin construir la cadena)
        proveedores = [n for n, _ in build_providers(SETTINGS, order=order, modelos={proveedor: modelo})]
    except Exception:
        proveedores = []  # ante cualquier error de config, se asume "nadie disponible"
    if proveedores:
        # first, *rest -> desempaquetado extendido: primario y lista de respaldos
        primario, *respaldo = proveedores
        etiqueta = PROVIDER_LABELS.get(primario, primario)  # .get evita KeyError
        if respaldo:
            # Muestra principal + respaldo (ej. "Principal: ✨ Gemini · Respaldo: ollama")
            st.success(f"Principal: {etiqueta} · Respaldo: {', '.join(respaldo)}")
        else:
            st.success(f"Usará únicamente: {etiqueta}")
        if primario != proveedor:
            # El usuario pidió X pero X no está disponible (p.ej. Gemini sin clave)
            st.warning(
                f"{PROVIDER_LABELS[proveedor]} no está disponible "
                f"{'(falta GOOGLE_API_KEY)' if proveedor == 'gemini' else '(error de configuración)'}; "
                f"se usará {PROVIDER_LABELS.get(primario, primario)}."
            )
    else:
        # Sin proveedores no se puede generar: el botón queda deshabilitado abajo
        st.error("No hay proveedores configurados. Revisa Ollama o GOOGLE_API_KEY en .env")

    # Widgets de entrada de contenido: nombre de app y contexto (variables del prompt)
    app_name = st.text_input("Nombre de la app", APP_NAME_DEFAULT)
    contexto = st.text_area("Contexto del proyecto", CONTEXT_DEFAULT, height=180)

    st.subheader("Cantidades")
    # number_input: spinner numérico; min/max acotan; value = inicial
    n_pasajero = st.number_input("Pasajero", min_value=0, max_value=20, value=6)
    n_conductor = st.number_input("Conductor", min_value=0, max_value=20, value=5)
    n_admin = st.number_input("Administrador", min_value=0, max_value=20, value=4)
    total = n_pasajero + n_conductor + n_admin  # suma para el caption informativo
    # markdown en caption: **negrita** renderizada por Streamlit
    st.caption(f"Total: {total} historias, en **una sola llamada** al modelo.")

# ───────────────────────── página principal ─────────────────────────
st.title("🚌 Generador de Historias de Usuario")
# caption: subtítulo pequeño bajo el título
st.caption("LangChain · Pydantic · Ollama local o Gemini API, con respaldo automático")

# st.session_state: dict-like que PERSISTE entre reruns de la sesión.
# Solo se inicializa la primera vez (guard con "not in").
if "historias" not in st.session_state:
    st.session_state.historias = None        # último resultado (HistoriasGeneradas | None)
    st.session_state.segundos = None         # duración de la última generación
    st.session_state.proveedor_usado = None  # qué proveedor respondió realmente

# st.button: True SOLO en el rerun donde se hizo click; disabled si no hay
# proveedores (el usuario ve el motivo en la barra lateral).
if st.button("Generar historias", type="primary", disabled=not proveedores):
    primario = proveedores[0] if proveedores else proveedor
    # Si el proveedor visible no es el que realmente está disponible, hay que
    # usar el modelo del .env de ESE primario (no el del input del sidebar)
    modelo_primario = modelo if primario == proveedor else (
        SETTINGS.ollama_model if primario == "ollama" else SETTINGS.gemini_model
    )
    # spinner: bloque de "esperando..." mientras corre el with (cierra al terminar)
    with st.spinner(f"Generando con {primario} ({modelo_primario})…"):
        try:
            chain = get_chain(proveedor, modelo)  # cadena cacheada (solo 1ª vez se arma)
            historias, segundos = generar_historias(  # ÚNICA llamada al LLM
                n_pasajero=int(n_pasajero),   # number_input puede devolver int|float
                n_conductor=int(n_conductor), # int() asegura entero para {n_...:02d}
                n_admin=int(n_admin),
                app_name=app_name,
                context=contexto,
                chain=chain,  # se inyecta la cadena ya cacheada (no se rearma)
            )
            # Persistir en sesión: el resto del script (y los reruns) podrán leerla
            st.session_state.historias = historias
            st.session_state.segundos = segundos
            st.session_state.proveedor_usado = primario
        except Exception as exc:  # noqa: BLE001 (cualquier fallo de red/modelo)
            # st.error muestra banner rojo; la app NO se cae, permite reintentar
            st.error(f"No se pudo generar: {exc}")

# Lee el resultado de la sesión (puede ser None en el primer render)
historias: HistoriasGeneradas | None = st.session_state.historias
if historias:  # truthy: objeto Pydantic no-vacío => hay resultado que mostrar
    usado = st.session_state.get("proveedor_usado")  # .get por seguridad (puede faltar)
    # Solo agrega el detalle del proveedor si lo sabemos
    detalle_prov = f" · con {PROVIDER_LABELS.get(usado, usado)}" if usado else ""
    # Banner de éxito con métricas: segundos con 1 decimal ({:.1f})
    st.success(f"Generado en {st.session_state.segundos:.1f} s · {len(historias.todas())} historias{detalle_prov}")

    # st.tabs: pestañas horizontales; devuelve 4 contenedores en el MISMO orden
    # que se le pasan los títulos (se desempaquetan con la misma cantidad).
    tab_pasajero, tab_conductor, tab_admin, tab_todas = st.tabs(
        [f"Pasajero ({len(historias.pasajero)})", f"Conductor ({len(historias.conductor)})",
         f"Administrador ({len(historias.administrador)})", "Todas"]
    )
    # Dibuja cada pestaña de rol con su lista asociada
    for tab, lista in [
        (tab_pasajero, historias.pasajero),
        (tab_conductor, historias.conductor),
        (tab_admin, historias.administrador),
    ]:
        with tab:  # `with` engancha el contenido al contenedor de la pestaña
            for h in lista:
                # markdown con negrita/itálica: **ID**, *rol*
                st.markdown(f"**{h.id}** — Como *{h.como}*, quiero {h.quiero}, para {h.para}.")

    with tab_todas:
        # DataFrame completo; hide_index quita la columna 0,1,2...
        # width="stretch" (ancho del contenedor) requiere Streamlit >= 1.49
        st.dataframe(to_dataframe(historias), hide_index=True, width="stretch")

    # st.columns(2) -> divide el ancho en 2 mitades; c1 y c2 son contenedores
    c1, c2 = st.columns(2)
    # download_button: solo aparece si hay data (estamos dentro de `if historias`)
    c1.download_button(
        "Descargar como texto (.txt)",
        to_texto(historias),            # data (str) que se escribe al descargar
        file_name="historias_usuario.txt",  # nombre sugerido al navegador
        mime="text/plain",              # tipo MIME -> el SO sabe que es texto
    )
    c2.download_button(
        "Descargar como CSV",
        # utf-8-sig: agrega BOM para que Excel muestre bien las tildes/ñ
        to_dataframe(historias).to_csv(index=False).encode("utf-8-sig"),
        # to_csv genera str; .encode() lo convierte a bytes (formato requerido
        # por download_button cuando se pasa data binaria)
        file_name="historias_usuario.csv",
        mime="text/csv",
    )
else:
    # Estado inicial: sin resultado aún, guía al usuario
    st.info("Ajusta las cantidades y el contexto en la barra lateral, y pulsa **Generar historias**.")

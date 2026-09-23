"""
Interfaz Streamlit del validador de historias de usuario.

Este archivo contiene la capa de presentacion (UI) de la aplicacion.
Utiliza Streamlit para crear una interfaz web interactiva que permite
validar historias de usuario contra criterios INVEST, detectar
ambiguedades y generar criterios de aceptacion.

Ejecutar con: streamlit run app.py

Arquitectura:
  app.py (UI) --> validador/graph.py (LangGraph) --> validador/nodes.py (nodos)
                                              |
                                     validador/llm.py (Gemini/Ollama)
"""
# ────────────────────────── IMPORTACIONES FUTURAS ──────────────────────────
# from __future__ import annotations habilita PEP 563 (Python 3.7+).
# SINTAXIS: Esta linea DEBE ser la primera declaracion del archivo (antes de docstrings).
# LOGICA: Permite usar anotaciones de tipo modernas como `str | None` en lugar
# de `Optional[str]` de typing. Las anotaciones se evaluan como strings en
# tiempo de ejecucion, evitando importar tipos pesados innecesariamente.
from __future__ import annotations

# ────────────────────────── IMPORTACIONES ESTANDAR ──────────────────────────
# dataclasses: Proporciona la funcion `replace()` para crear copias modificadas
# de dataclasses sin alterar la instancia original (inmutabilidad parcial).
# SINTAXIS: `dataclasses.replace(instancia, campo=nuevo_valor)` retorna una copia.
import dataclasses

# hashlib: Implementa algoritmos de hash criptograficos (MD5, SHA-256, etc.).
# SINTAXIS: Se usa para calcular el hash de la configuracion del .env.
# LOGICA: El hash permite detectar cambios en la configuracion y forzar
# la reconstruccion del grafo en el cache de Streamlit.
import hashlib

# ────────────────────────── IMPORTACIONES DE TERCEROS ──────────────────────────
# pandas: Libreria para manipulacion y analisis de datos en tablas (DataFrames).
# SINTAXIS: Se importa como `pd` por convencion (alias estandar de la comunidad).
# LOGICA: Se usa para crear tablas de resultados y exportar a CSV.
import pandas as pd

# streamlit: Framework para crear aplicaciones web interactivas en Python.
# SINTAXIS: Se importa como `st` por convencion (alias estandar de Streamlit).
# LOGICA: Toda la interfaz de usuario se construye con funciones de `st`.
import streamlit as st

# ────────────────────────── IMPORTACIONES DEL PROYECTO ──────────────────────────
# get_settings(): Lee la configuracion del archivo .env y retorna un objeto Settings.
# SINTAXIS: Funcion del modulo validador.config que retorna una instancia de Settings.
# LOGICA: Centraliza toda la configuracion (API keys, modelos, umbrales) en un solo lugar.
from validador.config import get_settings

# build_graph(): Construye el grafo de validacion con LangGraph.
# SINTAXIS: Funcion del modulo validador.graph que retorna un CompiledGraph.
# LOGICA: El grafo define el flujo: prevalidar -> relevancia -> analizar -> invest -> ambiguedad -> reescritura -> criterios -> finalizar.
from validador.graph import build_graph

# check_health(): Verifica la conectividad con los proveedores LLM (Gemini, Ollama).
# SINTAXIS: Funcion del modulo validador.llm que retorna un dict con el estado de cada proveedor.
# LOGICA: Se usa en la barra lateral para mostrar si los proveedores estan disponibles.
from validador.llm import check_health

# FinalResult: Modelo Pydantic que representa el resultado final de la validacion.
# SINTAXIS: Clase del modulo validador.schemas con campos tipados (veredicto, invest, ambiguedad, etc.).
# LOGICA: Se usa como tipo de retorno de `run_story()` para garantizar type safety.
from validador.schemas import FinalResult

# ────────────────────────── CONFIGURACION DE LA PAGINA ──────────────────────────
# st.set_page_config(): Configura los metadatos HTML de la pagina web.
# SINTAXIS: DEBE ser la primera funcion de Streamlit llamada en el script.
# LOGICA:
#   - page_title: Titulo que aparece en la pestana del navegador.
#   - page_icon: Emoji que aparece en la pestana (encodeado como Unicode).
#   - layout="wide": Usa el ancho completo de la pantalla (sin margenes estrechos).
st.set_page_config(page_title="Validador de Historias de Usuario", page_icon="🚌", layout="wide")

# ────────────────────────── CONTEXTOS Y CONSTANTES ──────────────────────────
# CONTEXTO_POR_DEFECTO: Texto descriptivo del proyecto que se usa como contexto
# para que el LLM evaluc si una historia es relevante.
# SINTAXIS: Variable global de tipo str, se usa en el text_area del sidebar.
# LOGICA: Primero intenta leer del .env (`_settings.project_context`). Si es None
# o vacio, usa el fallback hardcodeado. El operador `or` de Python retorna el primer
# valor "truthy" (no None, no vacio, no False).
_settings = get_settings()
CONTEXTO_POR_DEFECTO = _settings.project_context or (
    "BusetasApp Manizales: aplicacion para que los pasajeros conozcan las rutas, los horarios "
    "y dias de operacion de las busetas de Manizales y vean su ubicacion por GPS con el tiempo "
    "estimado de llegada. Roles: pasajero, conductor, administrador."
)

# EJEMPLOS: Diccionario con historias de ejemplo para mostrar en el selectbox.
# SINTAXIS: dict[str, str] donde la clave es el nombre del ejemplo y el valor es la historia.
# LOGICA: Permite al usuario cargar rapidamente un ejemplo para probar el validador.
#   - "Buena": Historia bien estructurada (rol + accion + beneficio).
#   - "Vaga": Historia sin claridad (ejemplo de lo que NO hacer).
#   - "Con detalles tecnicos": Historia con implementacion tecnica (anti-patron).
#   - "No es historia": Frase que no sigue el formato de historia de usuario.
EJEMPLOS = {
    "Buena": "HU-01: Como pasajero, quiero ver el recorrido de una ruta en el mapa, para saber por donde pasa antes de abordar.",
    "Vaga": "Como pasajero, quiero una app rapida y facil de usar, para usar las busetas mejor.",
    "Con detalles tecnicos": "Como administrador, quiero un boton que haga un INSERT en la base de datos MySQL, para agregar rutas.",
    "No es historia": "Hacer el backend en Django",
}

# VEREDICTOS: Diccionario que mapea cada veredicto con su etiqueta visual y funcion de Streamlit.
# SINTAXIS: dict[str, tuple[str, Callable]] donde:
#   - Clave: nombre del veredicto (str).
#   - Valor: tupla de (etiqueta con emoji, funcion de Streamlit para mostrar el mensaje).
# LOGICA: Permite renderizar el resultado con el color/icono correcto segun el veredicto.
#   - "aprobada": st.success (verde) - La historia cumple todos los criterios.
#   - "aprobada_con_observaciones": st.warning (amarillo) - Cumple pero con mejoras sugeridas.
#   - "requiere_reescritura": st.warning (amarillo) - No cumple INVEST, necesita reescritura.
#   - "rechazada": st.error (rojo) - Historia no valida para el proyecto.
#   - "no_relevante": st.warning (amarillo) - Historia de otro dominio (ej: Netflix, ecommerce).
#   - "no_evaluada": st.error (rojo) - Error tecnico, no se pudo evaluar.
VEREDICTOS = {
    "aprobada": ("✅ Aprobada", st.success),
    "aprobada_con_observaciones": ("🟡 Aprobada con observaciones", st.warning),
    "requiere_reescritura": ("🟠 Requiere reescritura", st.warning),
    "rechazada": ("❌ Rechazada", st.error),
    "no_relevante": ("🚫 No relevante para el proyecto", st.warning),
    "no_evaluada": ("⚠️ No evaluada (error tecnico)", st.error),
}


# ────────────────────────── RECURSOS CACHEADOS ──────────────────────────
# st.cache_resource: Decorador de Streamlit que cachea RECURSOS PESADOS (objetos grandes)
# que se crean una sola vez y se reutilizan en todas las recargas de la pagina.
# SINTAXIS: @st.cache_resource(show_spinner="Mensaje") muestra un spinner mientras se crea el recurso.
# LOGICA: El grafo de LangGraph es costoso de construir (carga modelos, define nodos, etc.).
# Se construye UNA SOLA VEZ y se reutiliza. El hash de settings invalida el cache si cambia .env.
@st.cache_resource(show_spinner="Construyendo el grafo...")
def get_graph(order: tuple[str, ...], settings_hash: str):
    """Construye y cachea el grafo de validacion con el orden de proveedores dado."""
    # dataclasses.replace(): Crea una COPIA de settings con el campo provider_order modificado.
    # SINTAXIS: replace(instancia, campo1=valor1, campo2=valor2) retorna nueva instancia.
    # LOGICA: No modificamos el original porque get_settings() retorna el mismo objeto (singleton).
    settings = dataclasses.replace(get_settings(), provider_order=order)
    # build_graph(): Construye el grafo LangGraph con los nodos y aristas definidos.
    # SINTAXIS: build_graph(settings) retorna un CompiledGraph listo para ejecutar.
    # LOGICA: El grafo incluye: prevalidar -> relevancia -> analizar -> invest -> ambiguedad -> reescritura -> criterios -> finalizar.
    return build_graph(settings=settings)


# st.cache_data: Decorador de Streamlit que cachea DATOS POR UN TIEMPO (TTL = Time To Live).
# SINTAXIS: @st.cache_data(ttl=20) cachea el resultado por 20 segundos.
# LOGICA: health() consulta Gemini y Ollama cada vez que se llama. Con TTL=20, solo consulta
# cada 20 segundos, evitando saturar los servidores con peticiones repetidas.
@st.cache_data(ttl=20)
def health():
    """Verifica la conectividad con los proveedores LLM (Gemini, Ollama)."""
    return check_health()


# ────────────────────────── EJECUCION DEL GRAFO ──────────────────────────
def run_story(graph, story: str, context: str, on_step=None) -> tuple[FinalResult, list[dict]]:
    """
    Ejecuta el grafo de validacion en modo streaming.

    SINTAXIS:
    - graph: CompiledGraph de LangGraph (el grafo construido por build_graph).
    - story: str con la historia de usuario en texto plano.
    - context: str con el contexto del proyecto (para evaluar relevancia).
    - on_step: Callable opcional que se ejecuta cuando termina cada nodo.
    - Retorna: tuple[FinalResult, list[dict]] (resultado + traza de ejecucion).

    LOGICA:
    1. graph.stream() ejecuta el grafo nodo por nodo, emitiendo updates.
    2. Cada update contiene el nombre del nodo y su payload (trace + result).
    3. Se extraen las entradas de traza y se acumulan en una lista.
    4. Si se proporciona on_step, se llama con cada entrada de traza (para UI en tiempo real).
    5. El resultado final (FinalResult) se extrae del ultimo payload que contenga "result".
    6. La asercion al final garantiza que el grafo siempre produce un resultado.
    """
    # trace: Lista que almacena cada paso de ejecucion del grafo (para auditoria y UI).
    trace: list[dict] = []
    # result: Almacena el resultado final del grafo. Inicia como None.
    result: FinalResult | None = None
    # graph.stream(): Ejecuta el grafo en modo streaming con el input inicial.
    # SINTAXIS: stream(dict_input, stream_mode="updates") retorna un generador de updates.
    # LOGICA: El dict contiene "raw_story" (historia cruda) y "project_context" (contexto del proyecto).
    for update in graph.stream({"raw_story": story, "project_context": context}, stream_mode="updates"):
        # update es un dict donde la clave es el nombre del nodo y el valor es su payload.
        for node, payload in update.items():
            # Extraemos las entradas de traza del payload (cada nodo agrega su entrada).
            for entry in (payload or {}).get("trace", []):
                trace.append(entry)
                # Si hay callback on_step, lo llamamos con la entrada actual (para UI en tiempo real).
                if on_step:
                    on_step(entry)
            # Si el payload contiene "result", es el resultado final del grafo.
            if payload and "result" in payload:
                result = payload["result"]
    # Asercion: Si el grafo termino sin resultado, algo fallo gravemente.
    # SINTAXIS: assert condicion, "mensaje_error" lanza AssertionError si condicion es False.
    assert result is not None, "El grafo termino sin resultado"
    return result, trace


# ICONO_ESTADO: Diccionario que mapea cada estado de ejecucion con su emoji correspondiente.
# SINTAXIS: dict[str, str] donde la clave es el estado y el valor es el emoji.
# LOGICA: Se usa en la traza del flujo para mostrar visualmente el estado de cada nodo.
#   - "ok": Nodo ejecutado exitosamente (check verde).
#   - "error": Nodo fallo durante la ejecucion (cruz roja).
#   - "skipped": Nodo omitido por una ruta condicional (flecha saltando).
ICONO_ESTADO = {"ok": "✅", "error": "❌", "skipped": "⏭️"}


# ────────────────────────── RENDERIZADO DE RESULTADOS ──────────────────────────
def render_result(r: FinalResult, trace: list[dict], key: str = "uno") -> None:
    """
    Renderiza el resultado completo de la validacion en la interfaz de Streamlit.

    SINTAXIS:
    - r: FinalResult con todos los campos de la validacion (veredicto, invest, ambiguedad, etc.).
    - trace: list[dict] con la traza de ejecucion del grafo (cada nodo que se ejecuto).
    - key: str unico para los widgets de Streamlit (evita conflicto de keys en modo lote).

    LOGICA:
    - Cada seccion se renderiza SOLO si el campo correspondiente existe en el resultado.
    - Esto permite que la UI se adapte dinamicamente al veredicto obtenido.
    - Si la historia no es relevante, se muestran menos secciones (solo relevancia + traza).
    """
    # Buscamos el veredicto en el diccionario VEREDICTOS para obtener la etiqueta y la funcion.
    # SINTAXIS: VEREDICTOS[r.veredicto] retorna (etiqueta_str, funcion_st).
    # LOGICA: Ejemplo: si r.veredicto = "aprobada", entonces etiqueta = "✅ Aprobada", caja = st.success.
    etiqueta, caja = VEREDICTOS[r.veredicto]
    # caja() es st.success, st.warning o st.error dependiendo del veredicto.
    # SINTAXIS: st.success("mensaje") muestra un recuadro verde con el mensaje.
    caja(f"**{etiqueta}** — {r.resumen}")

    # st.columns(4): Divide el area en 4 columnas de igual ancho para mostrar metricas.
    # SINTAXIS: st.columns(n) retorna n objetos Column que se usan como contenedores.
    # LOGICA: Muestra 4 metricas clave en una fila para una vision rapida del resultado.
    c1, c2, c3, c4 = st.columns(4)
    # c.metric(): Muestra una metrica con titulo, valor y opcionmente delta (cambio).
    # SINTAXIS: metric(label, value) donde value es str o None.
    # LOGICA: Se usa operador ternario para mostrar "—" si el campo es None.
    c1.metric("Promedio INVEST", f"{r.puntaje_invest}/5" if r.puntaje_invest is not None else "—")
    c2.metric("Ambiguedad", r.ambiguedad.nivel.capitalize() if r.ambiguedad else "—")
    c3.metric("Relevancia", f"{r.relevancia.puntaje_relevancia}/10" if r.relevancia else "—")
    c4.metric("Proveedor(es) LLM", ", ".join(r.proveedores_usados) or "ninguno")

    # Seccion de advertencias de prevalidacion.
    # LOGICA: Solo se muestra si hay advertencias (errores de formato como falta de "Como", "quiero", "para").
    if r.prevalidacion and r.prevalidacion.warnings:
        # st.expander(): Crea un contenedor colapsable que el usuario puede expandir.
        # SINTAXIS: expander(label) retorna un contexto manager.
        with st.expander(f"Advertencias de prevalidacion ({len(r.prevalidacion.warnings)})"):
            for w in r.prevalidacion.warnings:
                # st.write(): Renderiza texto con soporte de Markdown basico.
                st.write(f"- {w}")

    # Seccion de relevancia para el proyecto.
    # LOGICA: Solo se muestra si el LLM evaluo la relevancia (puede ser None si fallo).
    if r.relevancia:
        st.markdown("##### Relevancia para el proyecto")
        # st.columns([1, 3]): Divide en 2 columnas con proporcion 1:3 (25% / 75%).
        # LOGICA: La columna izquierda muestra el puntaje, la derecha la explicacion.
        col_rel1, col_rel2 = st.columns([1, 3])
        col_rel1.metric("Puntaje", f"{r.relevancia.puntaje_relevancia}/10")
        col_rel2.write(r.relevancia.explicacion)
        # Si el LLM identifico un area del proyecto, la muestra como caption.
        if r.relevancia.area_proyecto:
            st.caption(f"Area del proyecto: {r.relevancia.area_proyecto}")

    # Seccion de descomposicion de la historia (Rol, Accion, Beneficio).
    # LOGICA: Solo se muestra si el LLM descompuso la historia correctamente.
    if r.analisis:
        st.markdown("##### Descomposicion")
        a = r.analisis
        # st.write() con Markdown: Muestra los 3 componentes de la historia.
        # `or '—'`: Si el campo es None, muestra un guion como placeholder.
        st.write(f"**Rol:** {a.rol or '—'}  \n**Accion:** {a.accion or '—'}  \n**Beneficio:** {a.beneficio or '—'}")

    # Seccion de evaluacion INVEST.
    # LOGICA: Solo se muestra si el LLM evaluo los 6 criterios INVEST.
    if r.invest:
        st.markdown("##### Evaluacion INVEST")
        # pd.DataFrame(): Crea una tabla de pandas a partir de una lista de dicts.
        # SINTAXIS: DataFrame(list_of_dicts) donde cada dict es una fila.
        # LOGICA: Transforma los 6 criterios INVEST en una tabla legible para el usuario.
        df = pd.DataFrame(
            [
                # Dict comprehension: Crea un diccionario por cada criterio INVEST.
                # c.cumple es bool, se convierte a emoji con operador ternario.
                {"Criterio": k, "Puntaje": c.puntaje, "Cumple": "✅" if c.cumple else "❌",
                 "Justificacion": c.justificacion, "Sugerencia": c.sugerencia}
                # r.invest.items().items(): Itera sobre los 6 criterios (Ind, Negotiable, etc.).
                # SINTAXIS: r.invest es un dict[str, InvestCriterion], .items() retorna pares (key, value).
                for k, c in r.invest.items().items()
            ]
        )
        # st.dataframe(): Renderiza un DataFrame de pandas como tabla interactiva en Streamlit.
        # SINTAXIS: dataframe(df, hide_index=True) oculta la columna de indice numerico.
        st.dataframe(df, hide_index=True, width="stretch")

    # Seccion de ambiguedades detectadas.
    # LOGICA: Solo se muestra si hay items ambiguos en la historia.
    if r.ambiguedad and r.ambiguedad.items:
        st.markdown("##### Ambiguedades")
        for i in r.ambiguedad.items:
            # Cada ambiguedad se muestra en un expander con el fragmento problematico.
            with st.expander(f"«{i.fragmento}»"):
                # Muestra el problema detectado y la pregunta sugerida para el PO.
                st.write(i.problema)
                st.write(f"**Pregunta para el Product Owner:** {i.pregunta_aclaratoria}")

    # Seccion de reescritura de la historia.
    # LOGICA: Solo se muestra si el LLM sugirio una mejor version de la historia.
    if r.reescritura:
        st.markdown("##### Historia mejorada sugerida")
        # st.info(): Muestra un recuadro azul informativo con la historia mejorada.
        st.info(r.reescritura.historia_mejorada)
        # Lista de cambios realizados en la reescritura.
        for c in r.reescritura.cambios:
            st.write(f"- {c}")
        # Preguntas pendientes que el PO debe responder antes de aprobar.
        if r.reescritura.preguntas_pendientes:
            st.caption("Preguntas pendientes: " + " · ".join(r.reescritura.preguntas_pendientes))

    # Seccion de criterios de aceptacion (formato Gherkin: Dado/Cuando/Entonces).
    # LOGICA: Solo se muestra si el LLM genero criterios de aceptacion.
    if r.criterios:
        # Titulo dinamico: indica si los criterios son sobre la historia original o la mejorada.
        titulo = "Criterios de aceptacion" + (" (sobre la historia mejorada)" if r.reescritura else "")
        st.markdown(f"##### {titulo}")
        for c in r.criterios.criterios:
            # Renderiza cada criterio en formato Gherkin con Markdown.
            # SINTAXIS: f-string con saltos de linea `\\n` para formateo en Streamlit.
            st.markdown(f"**Escenario: {c.escenario}**  \n**Dado** {c.dado}  \n**Cuando** {c.cuando}  \n**Entonces** {c.entonces}")

    # Seccion de errores tecnicos.
    # LOGICA: Solo se muestra si hubo errores durante la ejecucion del grafo.
    if r.errores:
        with st.expander("Errores tecnicos", expanded=True):
            for e in r.errores:
                # st.code(): Renderiza texto con formato de codigo (monoespaciado, fondo gris).
                st.code(e)

    # ── Traza de ejecucion del grafo ──
    # LOGICA: Muestra todos los nodos que se ejecutaron, su estado, duracion y detalle.
    with st.expander("Traza del flujo"):
        # pd.DataFrame(trace): Convierte la lista de dicts en un DataFrame de pandas.
        # .assign(estado=...): Agrega una columna "estado" con los emojis de estado.
        # lambda d: d["status"].map(ICONO_ESTADO): Mapea cada status a su emoji.
        # [[...]]: Selecciona solo las columnas visibles (oculta las internas).
        st.dataframe(
            pd.DataFrame(trace).assign(estado=lambda d: d["status"].map(ICONO_ESTADO))[["node", "estado", "ms", "detail"]],
            hide_index=True,
            width="stretch",
        )
    # Boton para descargar el resultado completo como archivo JSON.
    # SINTAXIS: download_button(label, data, file_name, mime, key).
    # LOGICA: r.model_dump_json() serializa el modelo Pydantic a JSON indentado.
    st.download_button(
        "Descargar resultado (JSON)",
        r.model_dump_json(indent=2),
        file_name=f"{r.story_id or 'historia'}_resultado.json",
        mime="application/json",
        key=f"dl_{key}",
    )


# ────────────────────────── BARRA LATERAL (SIDEBAR) ──────────────────────────
# with st.sidebar: Crea un contenedor en la barra lateral izquierda de Streamlit.
# SINTAXIS: Context manager que agrupa todos los widgets dentro del sidebar.
# LOGICA: La sidebar contiene configuracion, estado de proveedores y contexto del proyecto.
with st.sidebar:
    st.header("⚙️ Configuracion")
    # st.radio(): Crea un grupo de botones de radio (seleccion unica).
    # SINTAXIS: radio(label, options, help) retorna el valor de la opcion seleccionada.
    # LOGICA: Permite elegir entre Gemini, Ollama o ambos proveedores.
    modo = st.radio(
        "Proveedor LLM",
        ["Automatico (Gemini → Ollama)", "Solo Gemini", "Solo Ollama"],
        help="En automatico, si Gemini falla (sin red, cuota, clave) se usa Ollama local.",
    )
    # Diccionario que traduce el modo seleccionado a una tupla de orden de proveedores.
    # SINTAXIS: dict comprension con clave = opcion del radio, valor = tupla de proveedores.
    # LOGICA: El orden importa: en modo automatico, se intenta Gemini primero y si falla, Ollama.
    orden = {"Automatico (Gemini → Ollama)": ("gemini", "ollama"), "Solo Gemini": ("gemini",), "Solo Ollama": ("ollama",)}[modo]

    # Muestra el estado de salud de cada proveedor LLM.
    # health() retorna un dict como {"gemini": {"ok": True, "detalle": "..."}, ...}
    estado = health()
    for nombre, info in estado.items():
        # Operador ternario: si info["ok"] es True, muestra circulo verde; si no, rojo.
        st.write(f"{'🟢' if info['ok'] else '🔴'} **{nombre.capitalize()}** — {info['detalle']}")
    # Boton para refrescar el estado de los proveedores (limpia el cache de health()).
    if st.button("Refrescar estado"):
        # health.clear(): Elimina el cache de la funcion health() para forzar una nueva consulta.
        health.clear()
        # st.rerun(): Re-ejecuta el script completo de Streamlit (refresca la pagina).
        st.rerun()

    # Campo de texto para que el usuario ingrese el contexto del proyecto.
    # SINTAXIS: text_area(label, value, height) retorna el texto ingresado por el usuario.
    # LOGICA: El contexto se usa para evaluar si una historia es relevante para el proyecto.
    contexto = st.text_area("Contexto del proyecto", CONTEXTO_POR_DEFECTO, height=180)
    try:
        settings = get_settings()
        # Hash de la configuracion para invalidar el cache cuando cambie .env.
        # SINTAXIS: hashlib.md5(string_bytes).hexdigest() retorna hash hexadecimal de 32 chars.
        # [:8]: Recorta a 8 caracteres (suficiente para detectar cambios).
        # LOGICA: Si el usuario cambia el modelo, la API key o la URL en .env, el hash cambia
        # y Streamlit reconstruye el grafo automaticamente (invalidacion de cache).
        settings_hash = hashlib.md5(
            f"{settings.gemini_model}{settings.ollama_model}{settings.ollama_base_url}"
            f"{settings.temperature}{settings.timeout_s}{settings.google_api_key}".encode()
        ).hexdigest()[:8]
        # get_graph(): Funcion cacheada que construye el grafo con el orden de proveedores y el hash.
        graph = get_graph(orden, settings_hash)
    except Exception as exc:  # noqa: BLE001
        # Si la construccion del grafo falla, muestra el error y detiene la ejecucion.
        st.error(f"No se pudo construir el grafo: {exc}")
        # st.stop(): Detiene la ejecucion del script actual (no muestra nada mas).
        st.stop()
    # Muestra el diagrama Mermaid del grafo (para fines educativos/debug).
    with st.expander("Ver grafo (Mermaid)"):
        # graph.get_graph().draw_mermaid(): Genera el codigo Mermaid del grafo LangGraph.
        st.code(graph.get_graph().draw_mermaid(), language="text")


# ────────────────────────── PAGINA PRINCIPAL ──────────────────────────
# Titulo y subtitulo de la aplicacion.
st.title("🚌 Validador de Historias de Usuario")
st.caption("LangGraph · LangChain · Pydantic · Gemini con respaldo en Ollama")

# st.tabs(): Crea pestanas navegables en la interfaz.
# SINTAXIS: tabs(["Pestana 1", "Pestana 2"]) retorna contenedores para cada pestana.
# LOGICA: Dos modos de uso: validar una historia individual o un lote de historias.
tab1, tab2 = st.tabs(["Una historia", "Lote (varias historias)"])

# ── Pestana 1: Una historia ──
with tab1:
    # st.selectbox(): Menu desplegable para seleccionar un ejemplo de historia.
    # SINTAXIS: selectbox(label, options) retorna el valor seleccionado.
    # LOGICA: ["—", *EJEMPLOS] crea una lista con "-" (sin ejemplo) y luego los nombres de los ejemplos.
    # *EJEMPLOS: Operador de desempaquetado que expande las claves del dict en la lista.
    ej = st.selectbox("Cargar ejemplo", ["—", *EJEMPLOS])
    # Campo de texto multilinea para ingresar la historia de usuario.
    # SINTAXIS: text_area(label, value, height, placeholder, key).
    # LOGICA: value=EJEMPLOS.get(ej, "") carga el ejemplo seleccionado (o vacio si es "—").
    # key: Identificador unico para el widget (necesario para evitar conflictos en reruns).
    texto = st.text_area(
        "Historia de usuario",
        value=EJEMPLOS.get(ej, ""),
        height=110,
        placeholder="Como [rol], quiero [accion], para [beneficio]",
        key=f"story_{ej}",
    )
    # Boton principal para ejecutar la validacion.
    # SINTAXIS: button(label, type="primary") crea un boton azul destacado.
    if st.button("Validar historia", type="primary", key="btn_uno"):
        # st.status(): Crea un contenedor con indicador de progreso animado.
        # SINTAXIS: status(label, expanded=True) muestra el estado expandido por defecto.
        # "as status": Asigna el contexto manager a la variable `status` para actualizarlo despues.
        with st.status("Ejecutando el flujo...", expanded=True) as status:
            # run_story(): Ejecuta el grafo y retorna (resultado, traza).
            # on_step: Lambda que se ejecuta por cada nodo, escribiendo el progreso en la UI.
            # ICONO_ESTADO[e["status"]]: Emoji del estado del nodo (ok, error, skipped).
            r, tr = run_story(
                graph, texto, contexto,
                on_step=lambda e: st.write(f"{ICONO_ESTADO[e['status']]} **{e['node']}** · {e['ms']} ms · {e['detail']}"),
            )
            # status.update(): Actualiza el estado del indicador de progreso.
            # LOGICA: Cambia el texto a "Flujo completado" y colapsa el contenedor.
            status.update(label="Flujo completado", state="complete", expanded=False)
        # render_result(): Renderiza el resultado completo de la validacion.
        render_result(r, tr, key="uno")

# ── Pestana 2: Lote de historias ──
with tab2:
    st.write("Pega una historia por linea (puedes incluir el prefijo HU-01:). Las lineas que empiezan con # se ignoran.")
    # Campo de texto para pegar multiples historias (una por linea).
    lote = st.text_area("Historias", height=220, key="lote")
    if st.button("Validar lote", type="primary", key="btn_lote"):
        # List comprehension: Filtra lineas vacias y comentarios (#).
        # l.strip() elimina espacios en blanco al inicio/final.
        # not l.strip().startswith("#") excluye lineas que son comentarios.
        historias = [l.strip() for l in lote.splitlines() if l.strip() and not l.strip().startswith("#")]
        if not historias:
            st.warning("Pega al menos una historia.")
        else:
            # st.progress(): Barra de progreso animada.
            # SINTAXIS: progress(0.0, text="Mensaje") inicia en 0%.
            barra = st.progress(0.0, text="Iniciando...")
            # Lista de tuplas (resultado, traza) para cada historia validada.
            resultados: list[tuple[FinalResult, list[dict]]] = []
            # enumerate(historias, 1): Itera con indice desde 1 (no desde 0).
            for n, h in enumerate(historias, 1):
                # Actualiza la barra de progreso en cada iteracion.
                # (n-1)/len(historias): Calcula el porcentaje completado.
                barra.progress((n - 1) / len(historias), text=f"Validando {n}/{len(historias)}")
                resultados.append(run_story(graph, h, contexto))
            # Marca la barra como completada (100%).
            barra.progress(1.0, text="Listo")
            # Crea un DataFrame de resumen con los resultados de todas las historias.
            resumen = pd.DataFrame(
                [
                    {
                        "ID": r.story_id or f"#{i}",
                        "Veredicto": VEREDICTOS[r.veredicto][0],  # [0] = etiqueta con emoji
                        "INVEST": r.puntaje_invest,
                        "Ambiguedad": r.ambiguedad.nivel if r.ambiguedad else "—",
                        "Historia": r.historia_original[:90],  # Trunca a 90 caracteres
                    }
                    for i, (r, _) in enumerate(resultados, 1)
                ]
            )
            # Muestra la tabla de resumen.
            st.dataframe(resumen, hide_index=True, width="stretch")
            # Boton para descargar el resumen como CSV.
            # resumen.to_csv(index=False): Convierte el DataFrame a CSV sin columna de indice.
            st.download_button("Descargar resumen (CSV)", resumen.to_csv(index=False), "resumen_historias.csv", "text/csv")
            # Muestra el detalle de cada historia en un expander colapsable.
            for i, (r, tr) in enumerate(resultados, 1):
                with st.expander(f"{r.story_id or f'#{i}'} — {VEREDICTOS[r.veredicto][0]}"):
                    render_result(r, tr, key=f"lote_{i}")

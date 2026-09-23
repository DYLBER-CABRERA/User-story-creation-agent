# Generador de Historias de Usuario (Ollama local o Gemini API)

Genera historias de usuario listas para backlog: 6 para pasajero, 5 para conductor,
4 para administrador (cantidades configurables). Puedes elegir en el programa si
conecta a **tu modelo local de Ollama** o a la **API de Gemini**, con respaldo
automático al otro proveedor si el principal falla.

## Por qué ya no se repiten las historias

Un modelo local pequeño a veces "rellena" la cantidad pedida copiando la primera
historia con distinto ID. Dos capas lo evitan:

1. **Tema obligatorio y distinto por historia** (`generador/temas.py`), tomado del
   documento de Alcances del proyecto: en vez de dejarle la diversidad al azar del
   modelo, se le asigna qué debe cubrir cada historia. Esto también mantiene todas
   las historias dentro del alcance de BusetasApp (nada de pagos, reservas, etc.).
2. **Validación con Pydantic + reintento automático**: `HistoriasGeneradas` rechaza
   cualquier salida con dos historias repetidas en el mismo rol; si el modelo repite,
   `with_retry` fuerza un segundo intento antes de rendirse (y si hay Gemini
   configurado, `with_fallbacks` prueba con él después).

## Por qué es rápido

1. **Una sola llamada al LLM**, no 15. El prompt pide las tres listas completas en una
   sola pasada: se paga una sola vez el costo fijo de cargar el modelo y el prompt.
2. **`method="json_schema"`** (por defecto en `langchain-ollama`): usa el parámetro
   `format` nativo de Ollama para forzar JSON, que es más liviano que el tool-calling
   que usan otros proveedores.
3. **`num_ctx` y `num_predict` acotados** en `.env`: el modelo no reserva ni genera
   más contexto del que necesita para 15 historias cortas.
4. **Prompt compacto**, sin ejemplos largos ni razonamiento pedido: solo reglas y
   formato. Los modelos locales chicos son más rápidos (y más precisos) con
   instrucciones cortas y directas.
5. **Respaldo a Gemini opcional** vía `with_fallbacks`, solo si configuras
   `GOOGLE_API_KEY`; si no, el sistema usa solo Ollama.

## Arquitectura del agente

El generador es una **cadena lineal de LLM (LCL)** con **una sola ejecución**:
no hay grafo de estados ni pasos intermedios con memoria. El flujo completo de
una petición es:

```
Entrada: app.py (Streamlit)  |  generador/cli.py (consola)
   │   cantidades por rol, nombre de la app, contexto,
   │   proveedor principal y modelo elegidos
   ▼
config.py ── Settings (dataclass congelada) leída de .env
   │         (modelos, temperature, num_ctx, num_predict, orden)
   ▼
llm.py ── build_providers() → lista ordenada [(primario), (respaldo)]
   │      ChatOllama (local) y/o ChatGoogleGenerativeAI (API);
   │      Gemini se omite si no hay GOOGLE_API_KEY
   ▼
generar.py ── build_chain():
   │
   │   prompts.py ── GENERATE_PROMPT (ChatPromptTemplate, un solo prompt
   │                 con las 3 listas y sus temas obligatorios)
   │        │
   │        ▼
   │   llm.with_structured_output(HistoriasGeneradas)
   │        │   · Ollama: method="json_schema" (format nativo)
   │        │   · with_retry(×2): si Pydantic rechaza (historias repetidas
   │        │     o mal formadas) → reintento automático
   │        │   · with_fallbacks: si el primario falla → respaldo
   │        ▼
   ▼
schemas.py ── HistoriasGeneradas validada (sin "quiero" repetido por rol)
   │
   ▼
Salida: (HistoriasGeneradas, segundos) → stdout / archivo .txt /
        pestañas + DataFrame + descargas .txt/.csv en Streamlit
```

**Capas por responsabilidad:**

| Capa | Archivo | Qué hace |
|---|---|---|
| Presentación | `app.py`, `generador/cli.py` | Interfaz Streamlit y consola (argparse); recogen la entrada y muestran el resultado |
| Configuración | `generador/config.py` | `Settings` inmutable cargada de `.env` (modelos, orden de proveedores, límites) |
| Proveedores LLM | `generador/llm.py` | Construye `ChatOllama` / `ChatGoogleGenerativeAI` en el orden elegido, con modelo editable por invocación |
| Orquestación | `generador/generar.py` | Arma la cadena (`prompt \| structured_output \| retry \| fallback`) y ejecuta la única `invoke()` |
| Contratos | `generador/schemas.py` | Modelos Pydantic de salida; validan la respuesta del modelo e impiden duplicados |
| Reglas de negocio | `generador/temas.py` | Temas obligatorios y distintos por historia (previene repetición y mantiene el alcance) |
| Prompt | `generador/prompts.py` | Un solo `ChatPromptTemplate` compacto para las tres listas |

### Nodos de estado

**Este producto no tiene nodos de estados.** El generador es una cadena única y
lineal (`prompt | modelo | retry | fallback`): no usa `StateGraph` de LangGraph,
no hay máquina de estados, ni estado compartido entre pasos intermedios. El único
"estado" es:

- el resultado `HistoriasGeneradas`, que se devuelve al terminar la llamada; y
- `st.session_state` de Streamlit, que solo conserva en la interfaz la última
  generación (historias, segundos y proveedor usados) para no perderla al
  interactuar con la página.

## Tecnologías utilizadas

| Tecnología | Versión requerida | Rol en el proyecto |
|---|---|---|
| **Python** | 3.12 | Lenguaje del proyecto (100 % Python, sin JS/TS) |
| **langchain-core** | `>=1.0` | Cadenas LCEL: `prompt \| modelo`, `with_structured_output`, `with_retry`, `with_fallbacks` |
| **langchain-ollama** | `>=1.0` | `ChatOllama`: modelo local vía `http://localhost:11434` con `json_schema`, `num_ctx` y `num_predict` acotados |
| **langchain-google-genai** | `>=3.0` | `ChatGoogleGenerativeAI`: API de Gemini como proveedor principal o de respaldo |
| **Pydantic** | `>=2.7` | Esquemas de salida y validación (detecta historias repetidas → fuerza reintento) |
| **python-dotenv** | `>=1.0` | Carga de variables de entorno desde `.env` |
| **Streamlit** | `>=1.50` | Interfaz gráfica (`app.py`): sidebar de configuración, pestañas por rol, tabla y descargas |
| **pandas** | `>=2.0` | DataFrame de historias y exportación a CSV (con BOM para Excel) |
| **pytest** | `>=8.0` | Pruebas unitarias con LLM simulado (sin llamadas reales) |

**Proveedores de modelos** (configurables en `.env`):

- **Ollama** — principal por defecto; corre en local (`ollama serve`), modelo
  `llama3.1:8b` con `num_ctx=4096` y `num_predict=1800` para máxima velocidad.
- **Gemini** — alternativa/respaldo vía `GOOGLE_API_KEY`, modelo
  `gemini-2.5-flash`; se omite automáticamente si no hay clave configurada.

El proyecto **no usa** base de datos, servidor API propio, Docker ni
cola de trabajos: Streamlit es el único servidor y el estado vive en memoria
por cada invocación.

## Instalación

```bash
cd generador-historias
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Ollama
```bash
ollama serve                 # si no corre como servicio
ollama pull llama3.1:8b      # o el modelo que prefieras
```
Modelos más chicos (ej. `llama3.1:8b`, `qwen2.5:7b`, `phi3:mini`) responden más rápido;
súbelo a algo mayor solo si la calidad del JSON no es suficiente.

### Variables de entorno
```bash
cp .env.example .env
```
Ajusta `OLLAMA_MODEL` al modelo que ya tengas descargado.

## Uso

### Consola
```bash
python -m pytest -q                          # pruebas sin LLM real

python -m generador.cli                      # 6 pasajero / 5 conductor / 4 administrador
python -m generador.cli --out historias.txt  # además, guarda el resultado en un archivo
python -m generador.cli --pasajero 8 --conductor 3 --administrador 5
python -m generador.cli --app "Mi App" --context "Descripción del proyecto..."

# Elegir proveedor principal y modelo (el otro queda de respaldo)
python -m generador.cli --provider ollama --model phi3:mini
python -m generador.cli --provider gemini --model gemini-2.5-flash
```

La consola imprime, al final (en stderr, no se mezcla con el resultado), cuánto tardó
la generación y con qué proveedor/modelo se hizo — útil para comparar modelos o
ajustar `OLLAMA_NUM_PREDICT`.

### Interfaz gráfica (Streamlit)
```bash
streamlit run app.py
```
Abre http://localhost:8501. En la barra lateral eliges el **proveedor**
(`🟢 Ollama (local)` o `✨ Gemini (API)`) y el **modelo** a usar (prellenado con el
del `.env`, editable); el otro proveedor queda como respaldo automático. También
defines el nombre de la app, el contexto y cuántas historias quieres por rol; el
botón "Generar historias" hace la única llamada al modelo y muestra el resultado en
pestañas por rol, una tabla completa y botones para descargar en `.txt` o `.csv`.
Si no hay ningún proveedor configurado (ni Ollama corriendo ni `GOOGLE_API_KEY`),
el botón queda deshabilitado y se explica el motivo arriba.

## Estructura

```
generador/
  config.py     Variables de entorno
  schemas.py    Pydantic: HistoriaUsuario y HistoriasGeneradas (valida sin repetidos)
  temas.py      Temas obligatorios por rol, tomados del documento de Alcances
  prompts.py    Un solo ChatPromptTemplate compacto
  llm.py        Construye Ollama/Gemini con orden y modelo elegibles (fallback)
  generar.py    Arma la cadena (json_schema + retry + fallback) y ejecuta UNA llamada
  cli.py        Interfaz de consola
app.py        Interfaz Streamlit
tests/test_generar.py   Pruebas con LLM simulado (incluye el caso de repetidos)
```

## Nota sobre tildes en el CSV

El CSV se descarga con BOM (`utf-8-sig`) para que Excel muestre bien las tildes y
la ñ. Si igual las ves mal en algún programa, al importar el CSV elige manualmente
la codificación UTF-8.

## Si quieres integrarlo con el validador

Cada historia generada (`h.texto`) ya viene en el formato
`"Como X, quiero Y, para Z"`, así que puedes pasarla directo al validador del otro
proyecto (`validador-historias`) sin transformarla.

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

# SPECs (especificaciones por funcionalidad, guía del Specification Agent)
python -m generador.cli --spec all --json historias.json   # genera y exporta las 12 SPECs
python -m generador.cli --spec rutas                       # solo SPEC-001
python -m generador.specs                                  # esqueleto desde el alcance (sin historias)
python -m generador.specs --historias historias.json       # SPECs completas desde un JSON guardado
python -m generador.specs --spec 003                       # una sola SPEC
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

Después de generar aparece la sección **Especificaciones (SPEC)**: un botón que
escribe las 12 SPECs en `docs/specs/`, un desplegable para previsualizar el
Markdown de cada una y un botón para descargarlas todas en `.zip`.

### Contexto que recibe el modelo

El campo "Contexto del proyecto" se **prellena desde `docs/alcance-contexto-proyecto.md`**
(fuente única de verdad) — en consola y en la app — con: §1 problema, §2 solución,
§3 objetivos, §4 público, §5 alcances, §6 fuera de alcance, §7 reglas de negocio,
§8 priorización, §9 roles, la §14 de RNF (solo filas con valor decidido) y las
decisiones humanas ya respondidas de `control.json`
(~5.3 KB, seguro para `OLLAMA_NUM_CTX=8192`).
Se excluyen §10 preguntas abiertas, los RNF `[por definir]` y §11-§13 (decisiones
pendientes: pasarlas al modelo lo invitaría a inventar valores, guía §8).
Sigue siendo editable a mano; `CONTEXT_DEFAULT` queda solo como respaldo si el
documento no existe.

### Especificaciones (SPEC)

Cada funcionalidad del proyecto tiene una SPEC con las 17 secciones de la guía
del Specification Agent (sección 7). Se arma de forma **determinista** (sin LLM)
a partir de `docs/alcance-contexto-proyecto.md` + las historias generadas:
requisitos, flujos, criterios de aceptación y trazabilidad salen de las historias;
contexto, reglas de negocio, fuera de alcance, restricciones y preguntas abiertas
salen del alcance. Lo que no está definido queda marcado como **Pendiente**
(nada se inventa, guía §11). Archivos: `docs/specs/SPEC-001-consulta-de-rutas.md`
… `SPEC-012-estadisticas-basicas.md`.

**RNF verificables (guía §8):** la **§6 de cada SPEC se lee de la §14 del
alcance** (`## 14. Requisitos no funcionales`), donde el equipo define los valores
medibles. Las filas marcadas **`[por definir]`** generan la pregunta `SUG-RNF`
(bloquea la aprobación hasta responderla); los valores decididos sí entran al
contexto del modelo de historias, los pendientes no (no se inventan cifras).

**Control humano (guía §12):** las preguntas abiertas (§15) deben responderse
antes de aprobar, y el estado de cada SPEC sigue el ciclo
`borrador v0.1 → APROBADA v1.0 → FROZEN`. Respuestas y estados se guardan en
`docs/specs/control.json` (compartido entre CLI y app):

```bash
python -m generador.specs --responder 001                 # responde en consola las preguntas (las de 001 incluyen sugerencias)
python -m generador.specs --responder                     # solo las globales (OPEN-Q + RNF)
python -m generador.specs --aprobar 001 --por "Prof. X"   # se niega si hay preguntas pendientes
python -m generador.specs --congelar 001                  # solo desde APROBADA
```

Dos capacidades adicionales al estilo de la guía:

- **§5 pasos 5-6 — preguntas sugeridas:** el agente genera preguntas (`SUG-*`)
  cuando detecta información faltante (valores RNF `[por definir]` en la §14 del
  alcance, casos límite sin analizar, dependencias pendientes, alcance ausente).
  Se muestran en la §15 y su respuesta humana alimenta directamente las §6, §10
  y §12 de la SPEC.
- **§2.8 gestión de cambios:** el contenido de cada SPEC aprobada/congelada se
  "huella" por secciones; si algo cambia al regenerar, la SPEC vuelve a borrador
  con **versión incrementada (1.0 → 1.1)** y el §17 registra qué secciones
  cambiaron (análisis de impacto). La re-aprobación sigue siendo humana.

En la app, la sección "Especificaciones (SPEC)" tiene el expander de preguntas
(abiertas + sugeridas de la SPEC seleccionada), la advertencia si se detectan
cambios en SPECs aprobadas, y los botones **Aprobar (v1.0)** / **Congelar (FROZEN)**;
aprobar queda deshabilitado mientras queden preguntas sin responder.

## Estructura

```
generador/
  config.py     Variables de entorno
  schemas.py    Pydantic: historia con flujos (normal, alternativo y excepción),
                criterios Dado/Cuando/Entonces y sin repetidos
  temas.py      Temas obligatorios por rol, tomados del documento de Alcances
  prompts.py    Prompt con reglas INVEST, flujos y criterios de aceptación
  llm.py        Construye Ollama/Gemini con orden y modelo elegibles (fallback)
  generar.py    Arma la cadena (json_schema + retry + fallback) y ejecuta UNA llamada
  specs.py      Catálogo de 12 SPECs y ensamblador de las 17 secciones (script propio)
  cli.py        Interfaz de consola (--spec / --json)
app.py        Interfaz Streamlit (incluye exportación de SPECs)
docs/alcance-contexto-proyecto.md   Fuente única de verdad del alcance
docs/specs/   Las 12 SPECs generadas (SPEC-001 … SPEC-012)
tests/test_generar.py   Pruebas con LLM simulado (incluye el caso de repetidos)
tests/test_specs.py     Pruebas del mapeo historia→SPEC y de las 17 secciones
```

## Nota sobre tildes en el CSV

El CSV se descarga con BOM (`utf-8-sig`) para que Excel muestre bien las tildes y
la ñ. Si igual las ves mal en algún programa, al importar el CSV elige manualmente
la codificación UTF-8.

## Si quieres integrarlo con el validador

Cada historia generada (`h.texto`) ya viene en el formato
`"Como X, quiero Y, para Z"`, así que puedes pasarla directo al validador del otro
proyecto (`validador-historias`) sin transformarla.

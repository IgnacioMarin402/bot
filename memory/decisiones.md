# Registro de decisiones

Formato: fecha — decisión — por qué. Añadir al final, no borrar entradas.

## 2026-07-03 — LangGraph + Python como base
Objetivo del proyecto: **aprender LangGraph** (State, nodos, aristas
condicionales, checkpointer). Python porque LangGraph es más maduro ahí.

## 2026-07-03 — Personalidad del bot: "Alejandro"
Jefe chileno burlón con 4 nodos: `chat` y `broma` (usan LLM), `once` y
`flojera` (respuesta fija). El router decide por palabras clave y largo del
mensaje.

## 2026-07-03 — Respuestas fijas sin LLM
`nodo_once` y `nodo_flojera` devuelven `AIMessage` directo. Por qué: pedirle
al LLM "repite exactamente X" no es confiable (improvisa en personaje), y la
respuesta fija es gratis, instantánea y determinista.

## 2026-07-03 — Arquitectura Ports & Adapters
`nucleo/` (lógica) separado de `interfaces/` (CLI hoy, WhatsApp mañana).
Regla: nucleo nunca importa de interfaces. Por qué: poder añadir canales sin
tocar la lógica.

## 2026-07-03 — Puerto del LLM = BaseChatModel de LangChain
No inventamos interfaz propia: todos los `ChatXxx` ya implementan
`BaseChatModel`. Adaptadores en `nucleo/llm/proveedores.py`, selector
`crear_llm()` por variable `LLM_PROVIDER`. Por qué: rotar de proveedor sin
tocar código (el dueño rotó Anthropic→Gemini→xAI→Groq→OpenRouter por límites
de créditos/free tiers durante el desarrollo).

## 2026-07-03 — Proveedor por defecto: OpenRouter con deepseek/deepseek-chat
Gratis (sufijo `:free` disponible), inteligente y estable. Nota aprendida:
los modelos `rerank`/`embed` NO sirven para chat; buscar `instruct`/`chat`.
Nota 2: sin `:free` en el slug se usa la versión de pago.

## 2026-07-03 — Memoria persistente con SqliteSaver
`memoria.sqlite` en la raíz (gitignored), conexión con
`check_same_thread=False` pensando en el futuro servidor web. Una
conversación = un `thread_id`; en WhatsApp será el número de teléfono.

## 2026-07-03 — Tooling: uv + poe + ruff
`pyproject.toml` + `uv.lock` (reproducible), tareas estilo npm (`poe dev`,
`prod`, `dev-watch`, `lint`, `format`, `graph`), ruff como linter+formatter.
Por qué: profesionalizar sin cambiar de framework; el stack LangGraph+FastAPI
ya es el correcto.

## 2026-07-04 — Grafo perezoso: `obtener_grafo()` con lru_cache
Antes, `import nucleo.grafo` creaba `memoria.sqlite` como efecto secundario
(construía el grafo al importar). Ahora el grafo es un singleton perezoso:
se construye en la PRIMERA llamada a `obtener_grafo()`. Regla derivada:
importar módulos no debe hacer I/O. Excepción deliberada: `config.py` crea el
`llm` al importar porque no hace I/O y valida la key al arranque (fail fast).

## 2026-07-05 — Router: matching por palabra completa (primer bug de usuario real)
Bug reportado en producción casera 😄: "entONCEs" disparaba el nodo `once`
porque el router usaba `in` (subcadenas). Fix: `_contiene_palabra()` con
regex `\b` (frontera de palabra); "11" tampoco matchea ya dentro de "2011".
Efecto secundario aprendido: las respuestas fijas repetidas contaminaron el
historial y el LLM del nodo chat empezó a IMITAR el patrón (contaminación de
contexto), copiando la frase fija VERBATIM (emojis incluidos) incluso DESPUÉS
del fix — la memoria persistente también persiste la contaminación; hay que
resetear el hilo afectado (DELETE del thread_id en checkpoints/writes).
Probar el router en aislamiento con casos esperados antes de tocar nodos:
los nodos estaban sanos. Verificado inspeccionando la memoria real con
grafo.get_state() por thread_id.

## 2026-07-04 — Imágenes por WhatsApp: visión multimodal, NO OCR
Cuando lleguen imágenes, se interpretarán pasándolas a un LLM con visión
(bloques de imagen en el mensaje), no con OCR aparte. Requiere proveedor
multimodal (el default actual `deepseek-chat` NO ve imágenes; Gemini Flash sí).
Se implementará DESPUÉS del webhook básico de WhatsApp, no antes.

# 📖 Documentación del proyecto — "Alejandro", un bot con LangGraph

> Guía completa para humanos: qué hace cada archivo, **por qué se construyó
> así**, y las lecciones que dejó el camino. Si el README es el "cómo arrancar",
> esto es el "cómo funciona y por qué".

---

## Índice

1. [Qué es este proyecto](#1-qué-es-este-proyecto)
2. [El mapa: cada archivo y su porqué](#2-el-mapa-cada-archivo-y-su-porqué)
3. [Glosario LangGraph: los 6 conceptos](#3-glosario-langgraph-los-6-conceptos)
4. [El viaje de un mensaje (flujos completos)](#4-el-viaje-de-un-mensaje)
5. [Decisiones de diseño clave](#5-decisiones-de-diseño-clave)
6. [Historia de bugs célebres (y sus lecciones)](#6-historia-de-bugs-célebres)
7. [Runbook: operación del día a día](#7-runbook-operación-del-día-a-día)

---

## 1. Qué es este proyecto

**Alejandro** es un chatbot con personalidad de jefe chileno burlón, construido
con **LangGraph** como proyecto de aprendizaje. Empezó como un script de
terminal y terminó respondiendo por **WhatsApp real** (Twilio + ngrok), con
memoria persistente por persona y arquitectura limpia.

El objetivo nunca fue el bot: fue **aprender LangGraph** (grafos, estado,
nodos, memoria) y de paso buenas prácticas de ingeniería Python. Por eso el
código tiene comentarios didácticos: explican conceptos, no solo instrucciones.

---

## 2. El mapa: cada archivo y su porqué

```
graph/
├── main.py                  # Punto de entrada
├── ver_grafo.py             # Utilidad: dibuja el grafo
├── pyproject.toml           # Manifiesto: dependencias + tareas + linter
├── uv.lock                  # Versiones exactas congeladas
├── .env / .env.example      # Secretos (real / plantilla)
├── CLAUDE.md                # Constitución del proyecto
├── memoria.sqlite           # La memoria del bot (generada)
├── memory/                  # Memoria del PROYECTO (humanos)
│   ├── decisiones.md
│   └── roadmap.md
├── nucleo/                  # ❤️ La lógica del bot
│   ├── config.py
│   ├── llm/
│   │   ├── __init__.py      # crear_llm(), nombre_proveedor(), tiene_vision()
│   │   └── proveedores.py   # los adaptadores de cada IA + registro VISION
│   ├── state.py
│   ├── nodos.py
│   ├── router.py
│   ├── tools.py             # funciones que el LLM puede pedir ejecutar
│   ├── mensajes.py          # construcción de mensajes multimodales (texto+imagen)
│   └── grafo.py
└── interfaces/              # 🔌 Las puertas de entrada
    ├── cli.py               # terminal
    └── whatsapp.py          # webhook Twilio (texto e imágenes)
```

### `main.py` — el punto de entrada

**Qué hace:** 3 líneas: importa `iniciar_cli()` y la llama.

**Por qué así:** un entry point debe ser mínimo y solo *delegar*. Toda la
inteligencia vive en módulos importables (así se puede testear, reutilizar y
agregar otros entry points sin duplicar nada).

### `nucleo/` — el corazón (no sabe que existe el mundo exterior)

La regla de oro del proyecto: **`nucleo/` jamás importa de `interfaces/`**.
El núcleo no sabe si le habla una terminal, WhatsApp o un test. Esto se llama
arquitectura **Ports & Adapters** (hexagonal) y es lo que permitió agregar
WhatsApp sin tocar UNA línea de la lógica.

#### `nucleo/state.py` — el State

**Qué hace:** define qué datos fluyen por el grafo: una lista de `messages` y
un campo opcional `temperatura`.

**Por qué así:** la anotación `Annotated[list, add_messages]` registra un
**reducer**: cuando un nodo devuelve mensajes nuevos, LangGraph los **agrega**
al historial en vez de reemplazarlo. Sin ese reducer, cada respuesta borraría
la conversación. Es el concepto más importante y el que más confunde al inicio.

`temperatura: NotRequired[float]` (2026-07-06) es el primer campo del State
que **no** es una lista de mensajes — un ejemplo de que el State puede llevar
cualquier dato que un nodo necesite. `NotRequired` (no todo turno la trae) es
distinto de un reducer con lista: acá no hay que "acumular" nada, LangGraph
simplemente usa el último valor escrito. Otros candidatos obvios para este
proyecto: nombre del usuario, idioma, contador de mensajes, humor del jefe.

#### `nucleo/nodos.py` — los nodos

**Qué hace:** 5 funciones, cada una recibe el State y devuelve **qué cambiar**:

| Nodo | Tipo | Comportamiento |
|------|------|----------------|
| `nodo_saludo` | FIJO | Presentación de Alejandro — solo la 1ª vez que un thread_id escribe |
| `nodo_chat` | LLM + tools | Conversa como Alejandro; puede pedir usar `hora_actual`/`tirar_dado` |
| `nodo_broma` | LLM | Una broma chilena sobre lo conversado (sin tools: tarea puntual) |
| `nodo_once` | FIJO | "JAJAJJA ENTONCES!!!" — sin llamar al LLM |
| `nodo_flojera` | FIJO | "Ya, vamos por un café..." — sin llamar al LLM |

**Por qué así:** la lección clave: **un nodo es solo una función Python** — no
está obligado a usar IA. Las respuestas fijas devuelven `AIMessage` directo:
gratis, instantáneas y 100% deterministas. Pedirle a un LLM "repite exactamente
esta frase" NO es confiable (improvisa). El prompt de Alejandro incluye además
una "vacuna" anti-imitación (ver [bugs célebres](#6-historia-de-bugs-célebres)).

`nodo_chat` usa `llm.bind_tools(TOOLS)` en vez de `llm` a secas: eso le informa
al modelo qué funciones existen. Solo `nodo_chat` las tiene — `nodo_broma` es
una tarea de una sola pasada, no necesita herramientas.

**Temperatura configurable (2026-07-06):** `nodo_chat` y `nodo_broma` leen
`state.get("temperatura")` y, si viene, hacen `.bind(temperature=x)` sobre el
modelo antes de invocarlo — `.bind()` no muta el cliente original, devuelve
una copia "pre-configurada" solo para esa llamada. Si el State no trae el
campo, cada nodo usa su propio default (`broma` es más creativa a propósito:
0.9 vs 0.7 de `chat`). Es el hook listo para una futura feature de "ajustar
la personalidad por conversación" sin tener que tocar `nucleo/config.py`.

**Ojo:** los nodos **nunca mutan** el state recibido; devuelven un dict parcial
y el reducer hace el merge.

#### `nucleo/tools.py` — herramientas que el LLM puede pedir usar

**Qué hace:** define `hora_actual()` y `tirar_dado(caras=6)` con el decorador
`@tool` de LangChain, y las junta en `TOOLS = [...]`.

**Por qué así:** el decorador `@tool` convierte una función Python normal en
algo que el modelo entiende — lee el nombre, los tipos y **el docstring** para
decidir cuándo y cómo llamarla (por eso el docstring no es opcional: es la
instrucción de uso). Se eligieron tools sin API externa ni costo — se prueban
en aislamiento con `.invoke({...})`, sin gastar el LLM.

#### `nucleo/mensajes.py` — mensajes multimodales (texto + imagen)

**Qué hace:** `mensaje_con_imagen(texto, bytes, mime_type)` arma un
`HumanMessage` con un bloque de texto y un bloque de imagen (data URI en
base64), el formato que entienden los proveedores con visión.

**Por qué vive en `nucleo/` y no en `interfaces/`:** el formato de bloques es
un detalle de cómo se le habla al LLM (LangChain), no de WhatsApp. Si mañana
existe una interfaz de Telegram, reutiliza esta misma función — solo cambia
CÓMO consigue los bytes de la imagen (eso sí es responsabilidad de cada
interfaz).

#### `nucleo/router.py` — la arista condicional

**Qué hace:** mira el último mensaje y devuelve el **nombre** del próximo nodo:

- contiene "urgente"/"por favor"/"necesito" → `broma`
- contiene "once"/"11" → `once`
- contiene una frase de **impedimento** ("tengo un problema", "no funciona",
  "me eché x", "cagué el deploy"...) → `flojera`
- si no → `chat`

**Por qué así:** esta función es el "if" del grafo — LangGraph la ejecuta en
tiempo real para elegir la rama. Usa `_contiene_palabra()` con regex `\b`
(frontera de palabra) porque buscar subcadenas con `in` produjo el bug más
famoso del proyecto ("entONCEs" disparaba el nodo `once`).

`flojera` originalmente se activaba por **largo del mensaje** (>30
caracteres); se cambió (2026-07-06) a detectar **impedimentos reales**, que es
lo que de verdad hace evadir a un jefe. Es una heurística por lista de frases
(`patrones_impedimento`), no un clasificador con LLM: gratis, instantánea y
testeable sin gastar API, pero no es exhaustiva — frases de impedimento muy
distintas a las listadas no matchean. Si esto limita, la evolución natural es
un nodo clasificador con LLM antes del router (ver `memory/roadmap.md`).

**El router siempre mira el último mensaje del USUARIO, no `[-1]` a secas**
(`_ultimo_mensaje_usuario()`, busca el `HumanMessage` más reciente). Esto
existe por un bug real (ver [bugs célebres](#6-historia-de-bugs-célebres)):
cuando se agregó el nodo `saludo`, el router se re-evalúa DESPUÉS de que
`saludo` ya agregó su propia respuesta al historial — mirar `[-1]` a ciegas
clasificaba el saludo del bot como si fuera la pregunta del usuario.

`es_primera_vez()` y `router_entrada()` (2026-07-06): la arista desde `START`
usa `router_entrada`, que intercepta el PRIMER mensaje de cada `thread_id` y
lo manda al nodo `saludo` antes que a cualquier otro. Detecta "primera vez"
con `len(state["messages"]) <= 1` — funciona porque, para cuando el grafo
empieza a correr, `state["messages"]` YA incluye el historial cargado del
checkpointer + el mensaje nuevo (el merge del reducer pasa ANTES de ejecutar
nodos). Si solo hay un mensaje, es porque no había historial previo.

#### `nucleo/grafo.py` — el ensamblador

**Qué hace:** une todo: registra los nodos (incluidos `saludo` y `tools`, un
`ToolNode`), conecta `START → router_entrada → nodos`, y compila con un
checkpointer **SqliteSaver** (memoria en disco). Expone `obtener_grafo()` y
`responder()`.

**Por qué así, pieza por pieza:**
- **`obtener_grafo()` con `@lru_cache`**: singleton perezoso. Importar el
  módulo NO crea archivos ni conexiones (import sin efectos secundarios); el
  grafo se construye la primera vez que alguien lo pide, una sola vez.
- **`SqliteSaver`** en vez de `MemorySaver`: la memoria sobrevive reinicios.
  El archivo `memoria.sqlite` se crea solo.
- **`check_same_thread=False`**: permite que el servidor web (FastAPI corre
  los handlers en hilos) use la misma conexión.
- **`START → saludo` (solo la 1ª vez) → se re-evalúa `router` → nodo real**:
  la primera vez que alguien escribe, pasa por `saludo` y LUEGO por el nodo
  que le corresponda según lo que preguntó — dejando DOS mensajes en el
  historial (presentación + respuesta real) en el mismo turno.
- **`chat` no va siempre a `END`**: usa `tools_condition` (prebuilt de
  LangGraph) para mirar si el LLM pidió una tool. Si sí → nodo `tools`; si no
  → `END`. Tras ejecutar la tool, `tools → chat` de vuelta, para que el LLM
  redacte la respuesta final con el resultado (el loop clásico "ReAct"). Los
  demás nodos (`once`, `broma`, `flojera`) siguen yendo directo a `END`: son
  de una sola pasada, no conversan con tools.
- **`responder(mensaje, thread_id) -> list[str]`**: invoca el grafo y
  devuelve solo los textos que hay que MOSTRARLE al usuario — puede ser más
  de uno (saludo + respuesta) y filtra los `ToolMessage`/`AIMessage` sin
  texto que deja el loop de tools (esos son pasos internos, no contenido
  final). Centralizado acá para que `cli.py` y `whatsapp.py` no dupliquen
  la lógica de "cuántos mensajes nuevos hay y cuáles son para mostrar".

#### `nucleo/config.py` — la configuración

**Qué hace:** carga el `.env` y expone `llm`, el modelo ya construido.

**Por qué así:** es el ÚNICO lugar del que el resto del código obtiene el LLM
(`from nucleo.config import llm`). Excepción consciente a la regla "import sin
efectos": construir el cliente LLM no hace I/O, y validar la API key al
importar es *fail fast* — mejor un error claro al arrancar que a mitad de
conversación.

#### `nucleo/llm/` — el puerto del modelo (rotar de IA sin tocar código)

**Qué hace:** `proveedores.py` tiene un **adaptador** por cada IA (OpenRouter,
Gemini, Claude, Groq, xAI) y un registro `PROVEEDORES = {nombre: función}`.
`__init__.py` tiene `crear_llm()`, que lee `LLM_PROVIDER` del `.env` y devuelve
el adaptador elegido.

**Por qué así:** es el patrón Strategy + inyección de dependencias (como los
providers de NestJS). El "puerto" no lo inventamos: todos los `ChatXxx` de
LangChain implementan la misma interfaz (`BaseChatModel`), por eso el grafo
funciona idéntico con cualquiera. Cambiar de IA = cambiar UNA línea del `.env`.
Este proyecto rotó 5 proveedores durante el desarrollo (por límites de créditos)
y el grafo jamás se enteró. Los imports dentro de cada función son a propósito:
si no tienes instalada una librería, solo falla ESE proveedor.

### `interfaces/` — los adaptadores de entrada

#### `interfaces/cli.py` — la terminal

**Qué hace:** bucle `input()` → `responder()` → `print` de cada texto
devuelto. Usa un `thread_id` fijo (una sola conversación).

**Por qué así:** fíjate que NO importa nodos, router ni tools — solo
`responder()` de `nucleo.grafo`. Una interfaz traduce entre "su mundo"
(teclado/pantalla) y el grafo, nada más. Como `responder()` puede devolver
más de un texto (ej. saludo + respuesta), el `for` imprime cada uno como un
mensaje separado — el mismo mecanismo que en WhatsApp se traduce en burbujas.

#### `interfaces/whatsapp.py` — el webhook

**Qué hace:** servidor FastAPI con dos endpoints:
- `GET /` → health check (`{"ok": true}`)
- `POST /whatsapp` → recibe el form de Twilio (`Body`, `From`, y si hay
  adjunto: `NumMedia`/`MediaUrl0`/`MediaContentType0`), invoca `responder()` y
  responde **TwiML** (el XML que Twilio entiende).

**Por qué así:**
- **`thread_id = From`** (el número del remitente): cada persona tiene su
  conversación separada, gratis, gracias al checkpointer. La feature estrella.
- **`def` y no `async def`**: FastAPI ejecuta funciones síncronas en un hilo
  aparte, así el `.invoke()` bloqueante no congela el servidor.
- **`try/except` con respuesta digna**: si el LLM falla (límites, red), el
  usuario recibe un mensaje en personaje, no silencio.
- **`twiml(textos: list[str])`** (2026-07-06): TwiML soporta VARIOS `<Message>`
  en una sola respuesta — Twilio los manda como burbujas de WhatsApp
  separadas. Por eso ya no recibe un string sino una lista: el saludo llega
  como un mensaje y la respuesta real como otro, en el mismo turno.

**Imágenes (2026-07-06):** cuando `NumMedia != "0"`, Twilio manda la URL del
adjunto **protegida con Basic Auth** (las credenciales de tu cuenta Twilio,
`TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN` en `.env`). El webhook:
1. Verifica `tiene_vision()` (¿el proveedor activo entiende imágenes?). Si no,
   responde un mensaje digno pidiendo texto — mejor eso que un error críptico.
2. Descarga los bytes con `httpx` (con Basic Auth).
3. Arma el mensaje con `nucleo.mensajes.mensaje_con_imagen()`.

La descarga (protocolo de Twilio) vive en la interfaz; el formato del mensaje
para el LLM (protocolo de LangChain) vive en `nucleo/` — la misma separación
de siempre. **Requiere `LLM_PROVIDER=gemini` o `claude`** (ver `VISION` en
`nucleo/llm/proveedores.py`); el default `openrouter/deepseek-chat` no ve imágenes.

### Los archivos de soporte

| Archivo | Qué es | Por qué existe |
|---------|--------|----------------|
| `pyproject.toml` | Manifiesto del proyecto | Dependencias declaradas, tareas `poe` (estilo npm scripts) y config de `ruff`. Un solo lugar. |
| `uv.lock` | Lockfile | Versiones EXACTAS congeladas → cualquiera reproduce el entorno con `uv sync`. |
| `.env` / `.env.example` | Secretos / plantilla | Las API keys JAMÁS van en el código ni en Git. La plantilla documenta qué variables existen, sin valores. |
| `CLAUDE.md` | Constitución | Reglas duras del proyecto (arquitectura, clean code, recetas). Los asistentes IA la cargan automáticamente → desarrollos futuros respetan lo construido. |
| `memory/decisiones.md` | Bitácora de decisiones | El "por qué" histórico. No se borran entradas: son la memoria del proyecto. |
| `memory/roadmap.md` | Próximos pasos | Qué sigue, qué está hecho, y la rutina de arranque de WhatsApp. |
| `memoria.sqlite` (+ `-wal`, `-shm`) | Memoria del BOT | Conversaciones guardadas por el checkpointer. Generado, gitignored. Los `-wal`/`-shm` son el "diario" de SQLite. |
| `ver_grafo.py` | Utilidad | Dibuja el grafo (Mermaid + PNG) — `uv run poe graph`. |
| `grafo.png` | Artefacto | El dibujo generado. Regenerable, gitignored. |

---

## 3. Glosario LangGraph: los 7 conceptos

1. **State** — el diccionario que fluye por el grafo. Aquí: `{messages: [...]}`.
2. **Reducer** (`add_messages`) — cómo se fusiona lo que devuelve un nodo con
   el estado existente. `add_messages` = "agrega, no reemplaces".
3. **Nodo** — función que recibe el State y devuelve un dict parcial. Puede
   usar un LLM... o no.
4. **Arista (edge)** — conexión fija: "después de X viene Y".
5. **Arista condicional** — una función (el `router`, o el prebuilt
   `tools_condition`) decide en runtime a qué nodo ir. Aquí vive la
   "inteligencia de flujo" del grafo.
6. **Checkpointer** — persistencia automática del State por conversación.
   Cada conversación se identifica con un **`thread_id`**: en CLI es fijo,
   en WhatsApp es el número de teléfono.
7. **Tool + ToolNode** — una función Python decorada con `@tool` que el LLM
   puede pedir ejecutar (`llm.bind_tools([...])`). `ToolNode` es el nodo
   prebuilt que la ejecuta de verdad y devuelve el resultado como mensaje.
   El patrón clásico es un loop: nodo LLM → (¿pidió una tool?) → `ToolNode`
   → vuelta al nodo LLM para redactar la respuesta final ("ReAct").

---

## 4. El viaje de un mensaje

### Por terminal (CLI)

```
Tú escribes "hola" (primera vez en este thread_id)
  → cli.py llama responder(HumanMessage("hola"), thread_id="yo-soy-el-jefe-malo")
      → responder() guarda cuántos mensajes había ANTES (0)
      → grafo.invoke({messages: [...]}, thread_id=...)
          → checkpointer CARGA el historial previo (vacío)
          → router_entrada ve que es la 1ª vez → "saludo"
          → nodo_saludo agrega su AIMessage fijo
          → se re-evalúa router (mirando el HumanMessage, no el saludo) → "chat"
          → nodo_chat: [ALEJANDRO_SYSTEM] + historial → llm.invoke() → respuesta
          → add_messages va agregando cada respuesta al historial
          → checkpointer GUARDA el nuevo estado en memoria.sqlite
      → responder() calcula el DELTA (2 mensajes nuevos) y devuelve sus textos
  → cli.py imprime cada texto: el saludo, después la respuesta
```

### Por WhatsApp

```
Tu novia escribe "hola" en WhatsApp
  → llega a los servidores de Twilio (número sandbox)
  → Twilio hace POST a tu URL de ngrok (.../whatsapp)
  → ngrok lo túnela hasta tu PC → FastAPI recibe Body="hola", From="whatsapp:+569..."
  → whatsapp.py: grafo.invoke(..., thread_id="whatsapp:+569...")
      → (mismo flujo interno de arriba, pero con SU historial, no el tuyo)
  → whatsapp.py responde TwiML: <Response><Message>...</Message></Response>
  → Twilio se lo entrega a su WhatsApp
```

**Detalle clave:** `.text` (no `.content`) para extraer la respuesta — algunos
proveedores devuelven el contenido como lista de bloques, y `.text` normaliza.

### Cuando Alejandro usa una tool

```
Tú preguntas "¿qué hora es?"
  → router → "chat"
  → nodo_chat: llm_con_tools.invoke(...) → el modelo responde con un
      AIMessage SIN texto pero CON tool_calls=[{name: "hora_actual", args: {}}]
  → tools_condition ve tool_calls → va al nodo "tools"
  → ToolNode ejecuta hora_actual() → agrega un ToolMessage con el resultado
  → vuelve a "chat" → nodo_chat: llm_con_tools.invoke(... + resultado de la tool)
      → esta vez responde con texto normal, usando el dato de la tool
  → END
```

### Cuando alguien manda una foto por WhatsApp

```
Tu amigo manda una foto + "¿qué es esto?"
  → Twilio incluye NumMedia=1, MediaUrl0=..., MediaContentType0=image/jpeg
  → whatsapp.py chequea tiene_vision() (requiere LLM_PROVIDER=gemini o claude)
  → descarga los bytes de MediaUrl0 con Basic Auth (credenciales de Twilio)
  → nucleo.mensajes.mensaje_con_imagen(texto, bytes, mime) arma el HumanMessage
      con un bloque de texto + un bloque de imagen (data URI base64)
  → grafo.invoke({messages: [ese mensaje]}, thread_id=su_numero)
      → router (mira .content de texto) → probablemente "chat"
      → nodo_chat: el LLM VE la imagen y responde sobre ella
  → TwiML de vuelta
```

---

## 5. Decisiones de diseño clave

(Registro completo con fechas en [memory/decisiones.md](memory/decisiones.md).)

- **Ports & Adapters**: la lógica no conoce sus interfaces → agregar WhatsApp
  costó un archivo, cero cambios al núcleo.
- **Puerto del LLM = `BaseChatModel`**: rotar de proveedor es editar el `.env`.
- **Respuestas fijas sin LLM**: determinismo y costo cero donde no se necesita IA.
- **`SqliteSaver`**: memoria que sobrevive reinicios; thread_id = teléfono en WhatsApp.
- **Import sin I/O** (`obtener_grafo()` perezoso): importar declara, no ejecuta.
- **uv + poe + ruff**: reproducibilidad, tareas homologadas, estilo consistente.
- **Verificar sin gastar API**: el router y los nodos fijos se prueban en
  aislamiento con keys dummy. El LLM real solo lo prueba un humano.

---

## 6. Historia de bugs célebres

Los bugs enseñaron más que los aciertos. Quedan documentados con honores:

### 🐛 El bug del "entONCEs" (2026-07-05)
**Síntoma:** el bot respondía "JAJAJJA ENTONCES!!!" a mensajes normales.
**Causa:** el router buscaba subcadenas: `"once" in "entonces"` es `True`.
**Fix:** matching por palabra completa con regex `\b`.
**Lección:** reproducir en aislamiento antes de refactorizar — el diagnóstico
tomó un test de 5 líneas sin gastar API; los nodos estaban sanos.

### 🧠 La contaminación de contexto (2026-07-05)
**Síntoma:** arreglado el router, el bot SEGUÍA respondiendo JAJAJJA a veces.
**Causa:** las respuestas fijas repetidas quedaron en el historial, y el LLM
del nodo chat —que es un completador de patrones— las **imitaba verbatim**,
emojis incluidos. La memoria persistente también persiste la basura.
**Fix:** doble — resetear el hilo contaminado (DELETE del thread_id en SQLite)
y "vacuna" en el prompt ("nunca repitas literalmente respuestas anteriores").
**Lección:** lo que entra al historial de un LLM es *entrenamiento en contexto*.
Curar la memoria importa tanto como escribir buenos prompts.

### 🔌 Guía rápida de errores del túnel (inspector ngrok, `localhost:4040`)

| Síntoma | Significado | Solución |
|---------|-------------|----------|
| `405 Method Not Allowed` | Llegó al servidor pero a la ruta equivocada | La URL en Twilio debe terminar en `/whatsapp` |
| `502 Bad Gateway` (~3ms) | Túnel OK, servidor local caído | `uv run poe dev-watch` |
| `504` / timeout | El LLM tardó >15s (límite de Twilio) | Reintentar; considerar modelo más rápido |
| ngrok pide versión mínima | El agente quedó viejo | `ngrok update` |

### 💳 La saga de los proveedores
Anthropic (Pro ≠ créditos de API) → Gemini (límite diario) → xAI (sin free
tier) → Groq (modelo chico) → **OpenRouter/DeepSeek** (actual). De frustración
a feature: gracias a esto existe el sistema multi-proveedor. Nota técnica:
los modelos `rerank`/`embed` no chatean; busca `chat`/`instruct`.

### 🖼️ El router que crasheaba con fotos (2026-07-06)
**Síntoma:** al construir el mensaje multimodal (`mensaje_con_imagen`) y
pasarlo por el router en un test, reventó con `AttributeError: 'list' object
has no attribute 'lower'`. **Causa:** con imágenes, `.content` es una LISTA
de bloques (texto + imagen), no un string — el router hacía `.content.lower()`.
**Fix:** usar `.text` (ya se usaba para mostrar respuestas), que normaliza a
string en ambos casos. **Lección:** se cazó ANTES de que llegara a
producción, probando el router con un mensaje de imagen simulado — mismo
método que el bug de "entONCEs": reproducir en aislamiento antes de asumir
que algo funciona.

### 👋 El saludo que confundía al router (2026-07-06)
**Síntoma:** al agregar el nodo `saludo` (presentación en el primer mensaje)
y volver a evaluar el router después, el test con `once` como primer mensaje
terminó yendo al nodo `chat` (que llama al LLM) en vez de a `once` (fijo).
**Causa:** el router miraba `state["messages"][-1]` a secas — pero para
cuando se re-evalúa DESPUÉS de `saludo`, el último mensaje es la propia
respuesta del bot ("Ah, llegaste..."), no lo que el usuario preguntó.
**Fix:** `_ultimo_mensaje_usuario()` busca hacia atrás el `HumanMessage` más
reciente, ignorando cualquier `AIMessage` que se haya agregado antes en el
mismo turno. **Lección:** un router basado en "el último mensaje" deja de
ser válido en cuanto el grafo tiene MÁS DE UN nodo antes de la decisión —
hay que ser explícito sobre DE QUIÉN es el mensaje que importa.

---

## 7. Runbook: operación del día a día

### Levantar el bot en WhatsApp
```powershell
uv run poe dev-watch     # terminal 1: el bot
ngrok http 8000          # terminal 2: el túnel
```
Pegar `https://<url-de-ngrok>/whatsapp` (¡con la ruta!) en Twilio → Sandbox
settings → "When a message comes in" (POST). La URL cambia en cada arranque
de ngrok. El join del sandbox expira cada 72 h (`join <código>` al número).

### Cambiar de IA
Editar `.env`: `LLM_PROVIDER=gemini` (u otro de `PROVEEDORES`) + su API key.

### Resetear la memoria
- **Un hilo:** `DELETE FROM checkpoints/writes WHERE thread_id='...'` en `memoria.sqlite`.
- **Todo:** parar el servidor y borrar `memoria.sqlite*`.

### Inspeccionar qué recuerda el bot
```python
from nucleo.grafo import obtener_grafo
estado = obtener_grafo().get_state({"configurable": {"thread_id": "whatsapp:+569..."}})
print(estado.values["messages"])
```

### Antes de dar por terminado un cambio
```powershell
uv run poe format && uv run poe lint
```
Y probar el router/nodos fijos con key dummy (sin gastar API). Las recetas para
agregar nodos/proveedores/interfaces están en [CLAUDE.md](CLAUDE.md).

---

*Documentación generada el 2026-07-05, con el bot ya vivo en WhatsApp y
habiendo sobrevivido a su primer usuario real (y a su novia). 🎉*

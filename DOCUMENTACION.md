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
│   │   ├── __init__.py      # crear_llm() — el selector
│   │   └── proveedores.py   # los adaptadores de cada IA
│   ├── state.py
│   ├── nodos.py
│   ├── router.py
│   └── grafo.py
└── interfaces/              # 🔌 Las puertas de entrada
    ├── cli.py               # terminal
    └── whatsapp.py          # webhook Twilio
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

**Qué hace:** define qué datos fluyen por el grafo: una lista de `messages`.

**Por qué así:** la anotación `Annotated[list, add_messages]` registra un
**reducer**: cuando un nodo devuelve mensajes nuevos, LangGraph los **agrega**
al historial en vez de reemplazarlo. Sin ese reducer, cada respuesta borraría
la conversación. Es el concepto más importante y el que más confunde al inicio.

#### `nucleo/nodos.py` — los nodos

**Qué hace:** 4 funciones, cada una recibe el State y devuelve **qué cambiar**:

| Nodo | Tipo | Comportamiento |
|------|------|----------------|
| `nodo_chat` | LLM | Conversa como Alejandro (personalidad en `ALEJANDRO_SYSTEM`) |
| `nodo_broma` | LLM | Una broma chilena sobre lo conversado |
| `nodo_once` | FIJO | "JAJAJJA ENTONCES!!!" — sin llamar al LLM |
| `nodo_flojera` | FIJO | "Ya, vamos por un café..." — sin llamar al LLM |

**Por qué así:** la lección clave: **un nodo es solo una función Python** — no
está obligado a usar IA. Las respuestas fijas devuelven `AIMessage` directo:
gratis, instantáneas y 100% deterministas. Pedirle a un LLM "repite exactamente
esta frase" NO es confiable (improvisa). El prompt de Alejandro incluye además
una "vacuna" anti-imitación (ver [bugs célebres](#6-historia-de-bugs-célebres)).

**Ojo:** los nodos **nunca mutan** el state recibido; devuelven un dict parcial
y el reducer hace el merge.

#### `nucleo/router.py` — la arista condicional

**Qué hace:** mira el último mensaje y devuelve el **nombre** del próximo nodo:

- mensaje >30 caracteres sin palabras clave → `flojera`
- contiene "urgente"/"por favor"/"necesito" → `broma`
- contiene "once"/"11" → `once`
- si no → `chat`

**Por qué así:** esta función es el "if" del grafo — LangGraph la ejecuta en
tiempo real para elegir la rama. Usa `_contiene_palabra()` con regex `\b`
(frontera de palabra) porque buscar subcadenas con `in` produjo el bug más
famoso del proyecto ("entONCEs" disparaba el nodo `once`).

#### `nucleo/grafo.py` — el ensamblador

**Qué hace:** une todo: registra los 4 nodos, conecta `START → router → nodos
→ END`, y compila con un checkpointer **SqliteSaver** (memoria en disco).

**Por qué así, pieza por pieza:**
- **`obtener_grafo()` con `@lru_cache`**: singleton perezoso. Importar el
  módulo NO crea archivos ni conexiones (import sin efectos secundarios); el
  grafo se construye la primera vez que alguien lo pide, una sola vez.
- **`SqliteSaver`** en vez de `MemorySaver`: la memoria sobrevive reinicios.
  El archivo `memoria.sqlite` se crea solo.
- **`check_same_thread=False`**: permite que el servidor web (FastAPI corre
  los handlers en hilos) use la misma conexión.

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

**Qué hace:** bucle `input()` → `grafo.invoke()` → `print`. Usa un `thread_id`
fijo (una sola conversación).

**Por qué así:** fíjate que NO importa nodos ni router — solo `obtener_grafo()`.
Una interfaz traduce entre "su mundo" (teclado/pantalla) y el grafo, nada más.

#### `interfaces/whatsapp.py` — el webhook

**Qué hace:** servidor FastAPI con dos endpoints:
- `GET /` → health check (`{"ok": true}`)
- `POST /whatsapp` → recibe el form de Twilio (`Body`, `From`), invoca el
  grafo y responde **TwiML** (el XML que Twilio entiende).

**Por qué así:**
- **`thread_id = From`** (el número del remitente): cada persona tiene su
  conversación separada, gratis, gracias al checkpointer. La feature estrella.
- **`def` y no `async def`**: FastAPI ejecuta funciones síncronas en un hilo
  aparte, así el `.invoke()` bloqueante no congela el servidor.
- **`try/except` con respuesta digna**: si el LLM falla (límites, red), el
  usuario recibe un mensaje en personaje, no silencio.
- El TwiML se arma a mano (5 líneas + `escape()`) para no sumar dependencias.

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

## 3. Glosario LangGraph: los 6 conceptos

1. **State** — el diccionario que fluye por el grafo. Aquí: `{messages: [...]}`.
2. **Reducer** (`add_messages`) — cómo se fusiona lo que devuelve un nodo con
   el estado existente. `add_messages` = "agrega, no reemplaces".
3. **Nodo** — función que recibe el State y devuelve un dict parcial. Puede
   usar un LLM... o no.
4. **Arista (edge)** — conexión fija: "después de X viene Y".
5. **Arista condicional** — una función (el `router`) decide en runtime a qué
   nodo ir. Aquí vive la "inteligencia de flujo" del grafo.
6. **Checkpointer** — persistencia automática del State por conversación.
   Cada conversación se identifica con un **`thread_id`**: en CLI es fijo,
   en WhatsApp es el número de teléfono.

---

## 4. El viaje de un mensaje

### Por terminal (CLI)

```
Tú escribes "hola"
  → cli.py lo envuelve en HumanMessage
  → grafo.invoke({messages: [...]}, thread_id="yo-soy-el-jefe-malo")
      → checkpointer CARGA el historial previo de ese thread
      → router mira el último mensaje → devuelve "chat"
      → nodo_chat: [ALEJANDRO_SYSTEM] + historial → llm.invoke() → respuesta
      → add_messages agrega la respuesta al historial
      → checkpointer GUARDA el nuevo estado en memoria.sqlite
  → cli.py imprime resultado["messages"][-1].text
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

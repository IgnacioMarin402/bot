# CLAUDE.md — Constitución del proyecto

Bot conversacional **"Alejandro"** (jefe chileno burlón) construido con **LangGraph**
como proyecto de aprendizaje. El dueño del proyecto está aprendiendo LangGraph:
al trabajar aquí, **explica los conceptos** que toques (nodos, estado, aristas,
checkpointer), no solo el código.

**Idioma del proyecto: español** — código, comentarios, docstrings y docs.

## Comandos

```powershell
uv sync                # instalar dependencias (desde uv.lock)
uv run poe dev         # correr el bot en terminal (CLI)
uv run poe prod        # servidor web WhatsApp (interfaces/whatsapp.py)
uv run poe dev-watch   # servidor web con auto-reload
uv run poe lint        # ruff check
uv run poe format      # ruff format
uv run poe graph       # dibujar el grafo (Mermaid + PNG)
```

Smoke test sin gastar API (keys dummy):

```powershell
$env:OPENROUTER_API_KEY = "dummy"; uv run python -c "from nucleo.grafo import obtener_grafo; obtener_grafo(); print('OK')"
```

## Arquitectura (Ports & Adapters) — reglas duras

```
main.py          → punto de entrada (mínimo, solo delega)
nucleo/          → lógica del bot. NO sabe de CLI ni WhatsApp
  config.py      → único lugar que expone `llm` (ya inyectado)
  llm/           → puerto+adaptadores del modelo (proveedores.py + crear_llm)
                   también: nombre_proveedor(), tiene_vision()
  state.py       → State (TypedDict + reducers + campos opcionales)
  nodos.py       → nodos del grafo
  router.py      → aristas condicionales
  tools.py       → funciones @tool que el LLM puede pedir ejecutar
  mensajes.py    → construcción de mensajes multimodales (texto+imagen)
  grafo.py       → ensambla y compila; expone `obtener_grafo()` y `responder()`
interfaces/      → adaptadores de entrada (cli.py, whatsapp.py)
memory/          → memoria del proyecto (decisiones y roadmap)
```

1. **`nucleo/` NUNCA importa de `interfaces/`.** Solo al revés.
2. Las interfaces consumen únicamente `responder()` (o `obtener_grafo()` si
   necesitan algo más fino, ej. `get_state()`) de `nucleo.grafo` — y mensajes
   de `langchain_core`. Nada de nodos/router directo. **Importar módulos no
   debe hacer I/O** (crear archivos, abrir conexiones, llamar red): el grafo
   es un singleton perezoso vía `lru_cache`. Validar config/keys al importar
   sí está permitido (fail fast, sin I/O).
3. **El LLM solo se instancia en `nucleo/llm/proveedores.py`.** El resto del
   código lo obtiene con `from nucleo.config import llm`. Prohibido crear
   `ChatXxx(...)` en otro lado. Para variar parámetros por nodo/conversación
   (ej. `temperature`), usar `.bind(...)` sobre `llm` — no crear otro cliente.
4. Los nodos devuelven **dicts parciales del State** (los reducers como
   `add_messages` acumulan). Nunca mutar el state recibido.
5. Respuestas fijas → devolver `AIMessage` directo en el nodo, **sin llamar
   al LLM** (determinismo y cero costo). No pedirle al LLM que "repita una frase".
6. **Secretos SOLO en `.env`** (gitignored). Jamás en código, logs ni commits.
   `.env.example` documenta las variables sin valores reales.
7. Una conversación = un `thread_id` del checkpointer. En WhatsApp es el
   número de teléfono.
8. Un router que decide según "el último mensaje" debe usar el último mensaje
   **del usuario** (`HumanMessage`), no `state["messages"][-1]` a secas — si
   un nodo previo en el mismo turno ya agregó su propia respuesta (ej.
   `saludo`), el último mensaje sería del bot, no del usuario. Ver
   `nucleo/router.py::_ultimo_mensaje_usuario` y la decisión 2026-07-06.

## Clean code del proyecto

- Nombres en español siguiendo el estilo existente: `nodo_x`, `crear_llm`,
  `construir_grafo`, `iniciar_cli`.
- Funciones pequeñas, una responsabilidad; módulos con docstring que explica
  el **por qué**, no solo el qué.
- Comentarios didácticos (este proyecto es para aprender): cuando un concepto
  de LangGraph aparece por primera vez, coméntalo.
- Antes de dar por terminado cualquier cambio:
  `uv run poe format` y `uv run poe lint` deben pasar limpios.
- Verificar sin gastar API: probar `router` y nodos fijos en aislamiento con
  keys dummy; el LLM real solo lo prueba el usuario a mano.
- No agregar dependencias sin registrarlas en `pyproject.toml` (usar `uv add`).

## Recetas

**Añadir un nodo:** función en `nucleo/nodos.py` → decidir cuándo se activa en
`nucleo/router.py` → registrarlo en `nucleo/grafo.py` (add_node + mapa de
conditional edges + edge a END) → probar el router en aislamiento.

**Añadir un proveedor de LLM:** función adaptador en `nucleo/llm/proveedores.py`
+ línea en `PROVEEDORES` → documentar la key en `.env.example` → dependencia
con `uv add langchain-<proveedor>`.

**Añadir una interfaz:** archivo nuevo en `interfaces/` que importe
`responder()` de `nucleo.grafo`. No tocar `nucleo/`.

## Memoria del proyecto (`memory/`)

- [memory/decisiones.md](memory/decisiones.md) — registro de decisiones (qué y por qué).
- [memory/roadmap.md](memory/roadmap.md) — próximos pasos acordados.

**Antes de un desarrollo nuevo:** leer ambos. **Al terminar uno relevante:**
añadir la decisión a `decisiones.md` (fecha + qué + por qué) y actualizar el
roadmap. No borrar entradas viejas: son la historia del proyecto.

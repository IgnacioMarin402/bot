# CLAUDE.md — Constitución del proyecto

Bot conversacional **"Alejandro"** (jefe chileno burlón) construido con **LangGraph**
como proyecto de aprendizaje. El dueño del proyecto está aprendiendo LangGraph:
al trabajar aquí, **explica los conceptos** que toques (nodos, estado, aristas,
checkpointer), no solo el código.

**Idioma del proyecto: español** — código, comentarios, docstrings y docs.

## Comandos

```powershell
uv sync                # instalar dependencias (desde uv.lock)
uv run poe dev         # Alejandro en terminal (CLI)
uv run poe dev-julieta # asistente de Daniela en terminal
uv run poe prod        # servidor web WhatsApp (ambos bots: /whatsapp y /julieta)
uv run poe dev-watch   # servidor web con auto-reload
uv run poe lint        # ruff check
uv run poe format      # ruff format
uv run poe graph       # dibujar el grafo (Mermaid + PNG)
```

Smoke test sin gastar API (keys dummy):

```powershell
$env:OPENROUTER_API_KEY = "dummy"; uv run python -c "from bots import obtener_bot; obtener_bot('alejandro'); obtener_bot('julieta'); print('OK')"
```

## Arquitectura (Ports & Adapters) — reglas duras

```
main.py          → punto de entrada: python main.py [alejandro|julieta]
nucleo/          → PLATAFORMA compartida (no sabe de bots ni interfaces)
  config.py      → único lugar que expone `llm` (ya inyectado)
  llm/           → puerto+adaptadores del modelo (proveedores.py + crear_llm)
                   también: nombre_proveedor(), tiene_vision(), tiene_audio()
  state.py       → State (TypedDict + reducers + campos opcionales)
  mensajes.py    → mensajes multimodales (texto+imagen+audio)
  limites.py     → protecciones: rate limit, tope de largo, ventana de jornada
  ejecucion.py   → responder(mensaje, thread_id, grafo) — usado por interfaces
bots/            → registro `obtener_bot(nombre)`; un paquete por bot
  alejandro/     → nodos, router, tools, grafo (memoria.sqlite)
  julieta/       → asistente ventas telco: almacen.py (datos_julieta.sqlite),
                   tools, nodos, grafo (agente puro, sin router), exportar.py
interfaces/      → adaptadores de entrada (cli.py, whatsapp.py — /whatsapp y /julieta)
memory/          → memoria del proyecto (decisiones y roadmap)
```

Son DOS bots (Alejandro y Julieta) — no generalizar a "N bots" sin necesidad.
Cada bot tiene memoria SQLite propia (memoria.sqlite / memoria_julieta.sqlite)
para que el mismo teléfono hable con ambos sin mezclar historiales.
Dependencias: `nucleo/` no importa de `bots/` ni `interfaces/`; `bots/` no
importa de `interfaces/`; `interfaces/` usa `obtener_bot()` + `responder()`.

1. **`nucleo/` NUNCA importa de `bots/` ni de `interfaces/`.** Solo al revés.
2. Las interfaces consumen únicamente `obtener_bot()` (de `bots`) +
   `responder()` (de `nucleo.ejecucion`) — y mensajes de `langchain_core`.
   Nada de nodos/router directo. **Importar módulos no debe hacer I/O**
   (crear archivos, abrir conexiones, llamar red): cada grafo es un singleton
   perezoso vía `lru_cache`. Validar config/keys al importar sí está
   permitido (fail fast, sin I/O).
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
   `bots/alejandro/router.py::_ultimo_mensaje_usuario` y la decisión 2026-07-06.
9. **Protecciones antes que el grafo**: rate limit y tope de largo se aplican
   en `responder()` ANTES de invocar (rechazar barato y temprano), y sus
   rechazos responden texto fijo SIN guardarse en el historial (evita costo
   y contaminación de contexto). Ver `nucleo/limites.py`.
10. **Tools que necesitan el `thread_id`** (ej. saber a qué usuario pertenece
    algo) declaran un parámetro `config: RunnableConfig` — LangChain lo
    inyecta solo, y el LLM NO lo ve en el schema (no es un argumento que el
    modelo decida). Ver `bots/julieta/tools.py::guardar_nombre`.
11. **Eliminar es peligroso, actualizar no**: toda tool que borre datos debe
    exigir confirmación explícita del usuario en el prompt/regla del sistema
    ANTES de llamarla (mostrar el registro, preguntar, esperar el "sí").
    Actualizar puede ir directo, pero confirmando el cambio en la respuesta.

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

**Añadir un nodo:** función en `bots/<bot>/nodos.py` → decidir cuándo se activa
(router del bot) → registrarlo en `bots/<bot>/grafo.py` (add_node + mapa de
conditional edges + edge a END) → probar el router en aislamiento.

**Añadir un proveedor de LLM:** función adaptador en `nucleo/llm/proveedores.py`
+ línea en `PROVEEDORES` → documentar la key en `.env.example` → dependencia
con `uv add langchain-<proveedor>`.

**Añadir una interfaz:** archivo nuevo en `interfaces/` que use
`obtener_bot()` de `bots` + `responder()` de `nucleo.ejecucion`. No tocar `nucleo/`.

**Añadir un bot:** carpeta en `bots/<nombre>/` con sus nodos/tools/grafo
(reutilizando `nucleo.config.llm`, `nucleo.state`, `nucleo.limites`) → rama en
`bots.obtener_bot()` → endpoint en `interfaces/whatsapp.py` + tarea `poe` si
aplica. Memoria SQLite propia por bot.

## Memoria del proyecto (`memory/`)

- [memory/decisiones.md](memory/decisiones.md) — registro de decisiones (qué y por qué).
- [memory/roadmap.md](memory/roadmap.md) — próximos pasos acordados.

**Antes de un desarrollo nuevo:** leer ambos. **Al terminar uno relevante:**
añadir la decisión a `decisiones.md` (fecha + qué + por qué) y actualizar el
roadmap. No borrar entradas viejas: son la historia del proyecto.

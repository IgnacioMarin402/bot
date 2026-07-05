# Chatbot "Alejandro" con LangGraph

Proyecto de aprendizaje para entender **LangGraph**: nodos, estado, aristas
condicionales y memoria. Un jefe chileno burlón que responde según lo que escribas.

> 📖 **¿Primera vez aquí?** Lee [DOCUMENTACION.md](DOCUMENTACION.md): qué hace
> cada archivo, por qué se construyó así, y las lecciones aprendidas.

## Primeros pasos

Este proyecto usa [uv](https://docs.astral.sh/uv/) (gestor) y
[poe](https://poethepoet.natn.io/) (task runner).

1. **Instala las dependencias** (crea el entorno desde el lockfile):
   ```powershell
   uv sync
   ```

2. **Configura tu API key** (¡nunca la subas a Git!):
   ```powershell
   Copy-Item .env.example .env
   ```
   Elige `LLM_PROVIDER` y pega la key correspondiente. Por defecto: OpenRouter
   (key GRATIS en https://openrouter.ai/keys).

3. **Ejecuta el bot:**
   ```powershell
   uv run poe dev
   ```
   Chatea. Prueba mensajes largos, o palabras como `once`/`11`, `urgente`,
   `por favor`. Escribe `salir` para terminar.

## Comandos (task runner)

| Comando | Qué hace |
|---------|----------|
| `uv run poe dev` | Corre el bot en la terminal (CLI) |
| `uv run poe prod` | Servidor web para WhatsApp *(requiere `interfaces/whatsapp.py`)* |
| `uv run poe dev-watch` | Servidor web con auto-reload al guardar |
| `uv run poe lint` | Revisa el código con ruff |
| `uv run poe format` | Formatea el código con ruff |
| `uv run poe graph` | Dibuja el grafo (Mermaid + PNG) |

Ver todas las tareas: `uv run poe`.

## WhatsApp (Twilio sandbox + ngrok)

Setup una sola vez:

1. **Twilio** (gratis): crea cuenta en https://www.twilio.com → consola →
   *Messaging → Try it out → Send a WhatsApp message*. Desde tu WhatsApp envía
   el código `join <palabras>` al número del sandbox para unirte.
2. **ngrok** (gratis): crea cuenta en https://dashboard.ngrok.com, copia tu
   authtoken y corre una vez: `ngrok config add-authtoken <tu-token>`.

Cada vez que quieras chatear:

```powershell
uv run poe dev-watch     # terminal 1: el servidor del bot
ngrok http 8000          # terminal 2: el túnel a internet
```

Copia la URL `https://xxxx.ngrok-free.app` que muestra ngrok y pégala en el
sandbox de Twilio (*When a message comes in*) como
`https://xxxx.ngrok-free.app/whatsapp` (método POST). Guarda… ¡y escríbele a
Alejandro por WhatsApp! Cada número tiene su propia memoria (`thread_id`).

## Estructura (arquitectura Ports & Adapters)

```
main.py                 # punto de entrada
pyproject.toml          # dependencias + tareas (poe) + config de ruff
nucleo/                 # la lógica del bot (no sabe de CLI ni WhatsApp)
  config.py             #   crea el LLM (lee .env)
  llm/                  #   Ports & Adapters del modelo
    proveedores.py      #     adaptadores (openrouter, gemini, claude...) + registro
    __init__.py         #     crear_llm(): selector según LLM_PROVIDER
  state.py              #   el State
  nodos.py              #   nodo_chat, nodo_broma, nodo_once, nodo_flojera
  router.py             #   la lógica de decisión (arista condicional)
  grafo.py              #   arma y compila el grafo (con memoria SQLite)
interfaces/             # adaptadores que hablan con el nucleo
  cli.py                #   bucle de terminal
  whatsapp.py           #   (futuro) webhook
```

**Regla de oro:** `nucleo/` nunca importa de `interfaces/`. Solo al revés.
Así se puede añadir WhatsApp sin tocar la lógica del bot.

| Concepto | Dónde |
|----------|-------|
| **State** | `nucleo/state.py` |
| **Nodes** | `nucleo/nodos.py` |
| **Conditional edge** | `nucleo/router.py` |
| **Graph + Checkpointer** | `nucleo/grafo.py` |

## Ideas para seguir aprendiendo

- Añade `interfaces/whatsapp.py` (FastAPI + Twilio) reutilizando el mismo grafo.
- Guarda más cosas en el `State` (humor del jefe, nombre del subordinado) y úsalas en los prompts.
- Añade *tools* (funciones que el LLM puede llamar) con `ToolNode`.
- Añade un nuevo proveedor de LLM: una función en `nucleo/llm/proveedores.py` + una línea en `PROVEEDORES`.

## Hecho ✅

- Multi-proveedor de LLM con Ports & Adapters (rota con `LLM_PROVIDER`).
- Memoria persistente en disco (`SqliteSaver` → `memoria.sqlite`).
- Tooling profesional: `uv` + `poe` + `ruff`.

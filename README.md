# Chatbot "Alejandro" con LangGraph

Proyecto de aprendizaje para entender **LangGraph**: nodos, estado, aristas
condicionales y memoria. Un jefe chileno burlón que responde según lo que escribas.

## Primeros pasos

1. **Configura tu API key** (¡nunca la subas a Git!):
   ```powershell
   Copy-Item .env.example .env
   ```
   Abre `.env` y pega tu key GRATIS de https://openrouter.ai/keys

2. **Ejecuta el bot:**
   ```powershell
   .\.venv\Scripts\python.exe main.py
   ```

3. Chatea. Prueba mensajes largos, o palabras como `once`/`11`, `urgente`,
   `por favor`. Escribe `salir` para terminar.

## Estructura (arquitectura Ports & Adapters)

```
main.py                 # punto de entrada
nucleo/                 # la lógica del bot (no sabe de CLI ni WhatsApp)
  config.py             #   crea el LLM (lee .env)
  state.py              #   el State
  nodos.py              #   nodo_chat, nodo_broma, nodo_once, nodo_flojera
  router.py             #   la lógica de decisión (arista condicional)
  grafo.py              #   arma y compila el grafo
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

- Cambia `MemorySaver` por `SqliteSaver` para memoria persistente en disco.
- Guarda más cosas en el `State` (humor del jefe, nombre del subordinado) y úsalas en los prompts.
- Añade `interfaces/whatsapp.py` (FastAPI + Twilio) reutilizando el mismo grafo.
- Añade *tools* (funciones que el LLM puede llamar) con `ToolNode`.

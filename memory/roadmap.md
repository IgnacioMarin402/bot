# Roadmap

Actualizar al terminar cada hito (mover a "Hecho" con fecha).

## Siguiente

1. **Endurecer webhook para producción** — validar firma `X-Twilio-Signature`.
2. **Router de impedimentos → clasificador con LLM** (opcional, si la lista de
   `patrones_impedimento` se queda corta): un nodo previo que le pregunte al
   LLM "¿esto es un impedimento sí/no?" en vez de matching por frases fijas.
   Trade-off: una llamada extra por mensaje (costo/latencia) a cambio de
   generalizar mejor. Ver nucleo/router.py.
3. **Multi-bot por ruta** (idea del usuario, 2026-07-06): un solo servidor
   FastAPI, pero el webhook elige QUÉ grafo invocar según el número de
   destino (`To` del payload Twilio) o un prefijo del mensaje. Cada "bot" es
   su propio grafo — no requiere rehacer nada, solo un nivel de selección
   arriba de `obtener_grafo()`.
4. (Opcional, si el bot pasa a "producción") Remitente propio de WhatsApp:
   número + verificación Meta Business → permite foto/nombre de perfil, y
   habilita más modelos de tools de pago. En sandbox NO se puede (número
   compartido de Twilio). Alternativa de infraestructura: VPS barato
   (Oracle free tier / Hetzner ~€4) reemplazando a ngrok para que el bot no
   dependa de que el laptop esté prendido.

## Rutina para levantar WhatsApp (recordatorio)

```powershell
uv run poe dev-watch   # terminal 1
ngrok http 8000        # terminal 2 -> URL nueva cada vez
```
Pegar `https://<url-ngrok>/whatsapp` (¡CON /whatsapp!) en Twilio → Sandbox
settings → "When a message comes in" (POST). El join del sandbox expira cada
72h: reenviar `join <código>` al +1 415 523 8886.

Para probar **imágenes**: `LLM_PROVIDER=gemini` (o `claude`) en `.env`, más
`TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN` (dashboard de Twilio → Account Info).

## Ideas (sin orden)

- Streaming de respuestas (`grafo.stream()`).
- Más tools: clima (requiere API key externa), búsqueda web, recordatorios.
- Más campos en el State: nombre del usuario, idioma, contador de mensajes,
  humor del jefe. `temperatura` ya sentó el precedente (campo opcional,
  `NotRequired`, sin reducer especial) — seguir ese mismo patrón.
- Forma de que el USUARIO cambie `temperatura` por chat (ej. "/temperatura 1.2"
  o una frase natural que el router detecte) — hoy solo tiene default por nodo.
- Modelo configurable por proveedor (`GEMINI_MODEL`, etc.) si hace falta.
- Combinar con MCP: un nodo del grafo podría usar un cliente MCP para llamar
  herramientas externas estandarizadas, en vez de (o además de) `nucleo/tools.py`.
  LangGraph = el flujo/orquesta; MCP = protocolo para exponer/consumir tools.
  No es necesario para lo que hay hoy (ToolNode nativo alcanza y es más simple).

## Hecho

- 2026-07-06: **Nodo `saludo` + multi-mensaje** — presentación fija en el
  primer mensaje de cada `thread_id` (`router_entrada`/`es_primera_vez` en
  `nucleo/router.py`), seguida de la respuesta real (saludo → re-evalúa
  `router` → nodo real). Se creó `nucleo/grafo.py::responder()` para
  centralizar "invocar + calcular mensajes nuevos + filtrar solo texto para
  el usuario", usado ahora por `cli.py` y `whatsapp.py` (que ya no llaman
  `grafo.invoke()` directo). `whatsapp.py::twiml()` acepta `list[str]` — un
  `<Message>` de TwiML por texto, Twilio los manda como burbujas separadas.
- 2026-07-06: **State: campo `temperatura`** — primer campo no-mensajes del
  State (`NotRequired[float]`). `nodo_chat`/`nodo_broma` la leen y hacen
  `.bind(temperature=x)` sobre el LLM; defaults distintos por nodo (broma
  más creativa). Hook listo para una futura preferencia por conversación.
- 2026-07-06: **Bug real: router confundía el saludo del bot con la pregunta
  del usuario** — al re-evaluarse después de `saludo`, `state["messages"][-1]`
  ya era la respuesta del bot. Fix: `_ultimo_mensaje_usuario()` busca el
  `HumanMessage` más reciente. Cazado con un test end-to-end antes de tocar
  producción.
- 2026-07-06: **Tools con ToolNode** — `nucleo/tools.py` (`hora_actual`,
  `tirar_dado`), `nodo_chat` usa `llm.bind_tools(TOOLS)`, grafo con loop
  `chat -> tools -> chat` vía `tools_condition` (prebuilt de LangGraph).
- 2026-07-06: **Imágenes por WhatsApp** — `nucleo/mensajes.py`
  (`mensaje_con_imagen`, formato OpenAI-compatible con data URI base64),
  `nucleo/llm` expone `tiene_vision()`/`VISION={"gemini","claude"}`,
  `interfaces/whatsapp.py` descarga el adjunto de Twilio (Basic Auth) y arma
  el mensaje multimodal. Requiere proveedor con visión.
- 2026-07-06: **Bug real cazado en revisión** — el router usaba `.content`
  (rompía con `AttributeError` en mensajes multimodales, donde `.content` es
  una lista de bloques, no string). Cambiado a `.text`. Cazado ANTES de
  llegar a producción, probando el router con un mensaje de imagen simulado.
- 2026-07-06: **Router: impedimentos en vez de largo** — `flojera` ya no se
  activa por mensaje >30 caracteres; ahora detecta frases de impedimento
  ("tengo un problema", "no funciona", "me eché x", jerga chilena como
  "cagué el deploy"). Heurística por lista de frases, no clasificador LLM
  (gratis y testeable offline). Ver limitación en nucleo/router.py.
- 2026-07-05: `DOCUMENTACION.md` — guía completa para humanos (mapa de
  archivos con porqués, glosario LangGraph, flujos, bugs célebres, runbook).
- 2026-07-05: Bug "entONCEs" arreglado (matching por palabra con \b) + hilo
  contaminado reseteado + vacuna anti-imitación en el prompt.
- 2026-07-04: 🎉 **ALEJANDRO EN WHATSAPP** — primera conversación real vía
  sandbox de Twilio + ngrok. Gotchas resueltos: ngrok de winget venía viejo
  (3.3.1 → `ngrok update` → 3.39.9) y la URL del sandbox debe incluir la ruta
  `/whatsapp` (sin ella: POST / → 405).
- 2026-07-04: `interfaces/whatsapp.py` (FastAPI + TwiML) probado localmente
  sin gastar API (rama fija `once`). Grafo perezoso (`obtener_grafo()`).
  ngrok instalado vía winget.
- 2026-07-03: CLI funcional con 4 nodos + router + memoria SQLite.
- 2026-07-03: Multi-proveedor LLM (openrouter/gemini/claude/groq/xai) vía `LLM_PROVIDER`.
- 2026-07-03: Tooling uv + poe + ruff.
- 2026-07-04: CLAUDE.md (constitución) + memory/ (decisiones y roadmap).

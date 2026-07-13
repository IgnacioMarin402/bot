# Roadmap

Actualizar al terminar cada hito (mover a "Hecho" con fecha).

## Siguiente

1. **Segundo número de Twilio** (en curso por el dueño, 2026-07-06): con dos
   números, cada uno apunta a su URL (`/whatsapp` y `/julieta`) y ambos bots
   viven a la vez. Configurar el webhook de cada número en Twilio. Ojo: el
   número nuevo necesita WhatsApp habilitado (verificación Meta Business) —
   si es un número solo-SMS no sirve directo.
2. **Julieta v3** (después de que Daniela la pruebe de verdad):
   - Enviar el Excel por WhatsApp (requiere hostear el archivo en URL pública
     y responder TwiML con `<Media>`).
   - Editar el nombre guardado si se equivocó (hoy `guardar_nombre` ya
     sobrescribe, pero no hay forma de pedir "cámbialo" explícitamente en el prompt).
3. **Endurecer webhook para producción** — validar firma `X-Twilio-Signature`
   (más importante ahora: pronto habrá datos reales de clientes en
   datos_julieta.sqlite).
4. **Router de impedimentos → clasificador con LLM** (opcional, si la lista de
   `patrones_impedimento` se queda corta). Ver bots/alejandro/router.py.
5. **Desplegar en Hetzner** siguiendo `deploy/GUIA.md` (decisión tomada:
   systemd + uv + Caddy + DuckDNS, sin Docker — ver decisiones 2026-07-06).
   Pasos del dueño: repo privado en GitHub + push, cuenta Hetzner (Ashburn),
   subdominio DuckDNS, y seguir la guía fase por fase. La validación de
   `X-Twilio-Signature` (punto 3) debe entrar ANTES de datos reales.
6. Después del VPS: migrar de Twilio a **Meta Cloud API** directo (más
   barato) = nueva interfaz `interfaces/meta.py` (JSON distinto + handshake
   GET de verificación); el grafo y las tools no se tocan.

## Rutina para levantar WhatsApp (recordatorio)

```powershell
uv run poe dev-watch   # terminal 1
ngrok http 8000        # terminal 2 -> URL nueva cada vez
```
Pegar en Twilio → Sandbox settings → "When a message comes in" (POST):
- `https://<url-ngrok>/whatsapp` para hablar con ALEJANDRO, o
- `https://<url-ngrok>/julieta` para hablar con JULIETA (asistente de Daniela).
(El sandbox tiene UN solo número → un bot activo a la vez; se cambia
re-pegando la URL. Con números propios de producción, cada bot tendría el
suyo.) El join del sandbox expira cada 72h: reenviar `join <código>` al
+1 415 523 8886.

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

- 2026-07-06: **Rename daniela → julieta + nombre por usuario + update/delete**
  — `bots/daniela/` → `bots/julieta/` (git mv, historial preservado); BD
  renombradas (`datos_julieta.sqlite`, `memoria_julieta.sqlite`); endpoint
  `/julieta`, `poe dev-julieta`. Tabla `usuarios(telefono→nombre)`:
  `router_entrada(state, config)` decide por el ALMACÉN (no por el mensaje)
  si hace falta `nodo_saludo` (fijo, pide el nombre); tool `guardar_nombre`
  recibe el `thread_id` vía `config: RunnableConfig` inyectado (invisible
  para el LLM); `nodo_asistente` arma system prompt dinámico con/sin nombre.
  Nuevas tools `actualizar_registro`/`eliminar_registro` con whitelist
  `CAMPOS_EDITABLES`; eliminar exige confirmación explícita (regla de
  prompt). Verificado offline: almacén, tools con config, router_entrada
  (3 casos), end-to-end (saludo fijo sin gastar API), regresión Alejandro,
  webhook con ambos endpoints.
- 2026-07-06: **Refactor de carpetas** — Alejandro movido a `bots/alejandro/`
  (lista de impedimentos del dueño preservada); `nucleo/` quedó como
  plataforma pura con `ejecucion.py::responder(mensaje, thread_id, grafo)`.
  Regla de dependencias: nucleo ← bots ← interfaces. `poe graph <bot>`.
- 2026-07-06: **Exportación a Excel** — `poe exportar` genera
  exports/daniela_<fecha>.xlsx (una hoja por categoría, openpyxl). Probado
  end-to-end: insertar → exportar → releer.
- 2026-07-06: **Notas de voz** — `mensaje_con_audio()` (bloque "media" de
  Gemini, formato verificado en la fuente de la librería), `tiene_audio()`
  (`AUDIO={"gemini"}`), webhook distingue image/audio/otro por content-type
  con rechazos dignos. Requiere `LLM_PROVIDER=gemini`.
- 2026-07-06: 🤖🤖 **SEGUNDO BOT: DANIELA** — asistente de ventas telco en
  `bots/daniela/` (almacén SQLite + 6 tools + agente puro sin router).
  Webhook con dos endpoints: `/whatsapp` (Alejandro) y `/daniela`. CLI:
  `poe dev-daniela`. `responder()` ahora acepta `grafo=` (default Alejandro).
  Memorias separadas por bot. Probado offline: almacén, tools, ambos grafos,
  regresión de Alejandro y ambos endpoints en el mismo servidor.
- 2026-07-06: **Protecciones anti-abuso** (`nucleo/limites.py`): rate limit
  10 msg/min por thread_id (ventana deslizante), tope de 10.000 caracteres,
  y ventana de jornada de 8 h (el LLM solo ve los mensajes recientes; la
  memoria completa sigue en SQLite). Aplicadas en `responder()` antes de
  invocar el grafo; los rechazos responden texto fijo sin tocar el historial.
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

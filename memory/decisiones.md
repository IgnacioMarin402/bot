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

## 2026-07-06 — Router: `flojera` por impedimento, no por largo
Cambio pedido por el dueño: el trigger de 30 caracteres era arbitrario y no
capturaba la intención real ("el jefe evade cuando hay un PROBLEMA, no
cuando el mensaje es largo"). Se reemplazó por `patrones_impedimento`: lista
de frases típicas en español + jerga chilena ("tengo un problema", "no
funciona", "me eché x", "cagué el deploy"). Es heurística, no un clasificador
LLM — se decidió así para mantener el router gratis, instantáneo y testeable
sin gastar API (consistente con el resto del proyecto). Riesgo aceptado:
frases de impedimento no listadas no matchean; evolución natural si esto
limita = nodo clasificador con LLM antes del router (ver roadmap).

## 2026-07-06 — Bug real: router con `.content` rompía en mensajes multimodales
Al construir el mensaje con imagen (`nucleo/mensajes.py`), `.content` pasa a
ser una LISTA de bloques (texto + imagen), no un string. El router hacía
`.content.lower()` → `AttributeError`. Se cambió a `.text` (misma propiedad
que ya se usaba para mostrar respuestas), que normaliza a string en ambos
casos. Cazado ANTES de producción probando el router con un mensaje
multimodal simulado — mismo método que el bug de "entONCEs": reproducir en
aislamiento antes de asumir que algo funciona.

## 2026-07-06 — Imágenes: visión vive en nucleo/mensajes.py, descarga en interfaces/whatsapp.py
Separación deliberada: el FORMATO del mensaje multimodal (bloques de texto +
imagen en base64) es un detalle de cómo se habla con el LLM (LangChain) →
vive en `nucleo/`, reutilizable por cualquier interfaz futura. La DESCARGA del
adjunto (URL protegida con Basic Auth de Twilio) es un detalle de WhatsApp →
vive en `interfaces/whatsapp.py`. `nucleo/llm` expone `tiene_vision()` para
que el webhook rechace con un mensaje digno si el proveedor activo no ve
imágenes, en vez de un error críptico del LLM. `VISION = {"gemini", "claude"}`
(verificado: gemini-2.0-flash y claude-haiku-4-5 son multimodales; los demás
proveedores configurados hoy —deepseek-chat, llama-3.3-70b, grok-3— no están
confirmados con visión).

## 2026-07-06 — Tools con ToolNode: `hora_actual` y `tirar_dado`
Primeras tools del proyecto, elegidas sin API externa ni costo (se prueban
en aislamiento con `.invoke({...})`, sin gastar el LLM). Solo `nodo_chat` usa
`llm.bind_tools(TOOLS)` — `nodo_broma` es una tarea de una sola pasada, no
necesita herramientas. Grafo: `chat` ya no va siempre a `END`; usa
`tools_condition` (prebuilt de LangGraph) para decidir entre `END` y el nodo
`tools` (un `ToolNode`), con loop de vuelta `tools → chat` para que el LLM
redacte la respuesta final con el resultado (patrón ReAct estándar).

## 2026-07-06 — State: campo `temperatura` (NotRequired) + primer uso real
Respuesta a "¿qué más podría viajar en el State?": se agregó `temperatura:
NotRequired[float]`, sin reducer especial (LangGraph usa "último valor
escrito"). `nodo_chat`/`nodo_broma` la leen con `state.get("temperatura",
default_del_nodo)` y hacen `.bind(temperature=x)` sobre el LLM (no muta el
cliente compartido). Defaults distintos por nodo (`broma`=0.9 > `chat`=0.7)
para que el campo tenga un efecto visible desde ya, sin construir todavía un
mecanismo para que el usuario la cambie por chat (queda en roadmap si hace
falta). Otros candidatos discutidos y NO implementados aún: nombre del
usuario, idioma, contador de mensajes, humor del jefe.

## 2026-07-06 — Nodo `saludo`: presentación en el primer mensaje + multi-mensaje
Pedido del dueño: que Alejandro se presente la primera vez y "mande 2
mensajes". Diseño: `router_entrada` (nueva arista desde START) detecta
`es_primera_vez()` (`len(state["messages"]) <= 1`, válido porque el reducer
ya fusionó historial+mensaje nuevo ANTES de correr nodos) y manda a `saludo`
(nodo fijo); desde `saludo` se re-evalúa el `router` normal para llegar al
nodo que corresponda de verdad. Efecto: la primera interacción dejó DOS
`AIMessage` en el historial en el mismo turno (presentación + respuesta).
Para que las interfaces pudieran mostrar AMBOS (no solo el último mensaje),
se creó `nucleo/grafo.py::responder()` — centraliza "invocar + calcular qué
mensajes son nuevos + filtrar solo los de texto para el usuario" en un solo
lugar, reemplazando las llamadas directas a `grafo.invoke()` en `cli.py` y
`whatsapp.py`. TwiML de Twilio soporta varios `<Message>` en una respuesta
(Twilio los entrega como burbujas separadas), así que `whatsapp.py::twiml()`
pasó de recibir un string a recibir `list[str]`.

## 2026-07-06 — Protecciones anti-abuso: `nucleo/limites.py`
Tres defensas, todas testeables sin API (pedido del dueño tras entender los
rate limits de los proveedores). Principio rector: **rechazar lo más barato
posible, lo más temprano posible** — un `if` cuesta nanosegundos, el LLM
cuesta plata. Se aplican en `responder()` ANTES de invocar el grafo, y sus
rechazos NO se guardan en el historial (lección de la contaminación).
1. **Rate limit**: 10 mensajes/min por `thread_id`, ventana deslizante en
   memoria (dict + deque + Lock porque FastAPI usa hilos). Se eligió 10 y no
   15: 1 msg/6 s sobra para un humano, asfixia a un script. Producción
   multi-proceso necesitaría Redis — innecesario hoy.
2. **Tope de largo**: 10.000 caracteres. Se chequea ANTES que el rate limit
   para que un mensaje gigante rechazado no consuma cupo.
3. **Ventana de jornada (8 h)**: los nodos con LLM envían solo los mensajes
   de las últimas 8 h ("la jornada laboral de Alejandro") vía
   `recortar_jornada()`. La memoria completa sigue en SQLite: se limita lo
   que el LLM VE, no lo que el bot recuerda. Sin esto el costo por turno
   crece para siempre (el historial completo se re-envía en cada mensaje).
   Detalle técnico: los mensajes de LangChain no traen timestamp — se
   estampan en `responder()` (`additional_kwargs["marca_tiempo"]`, que el
   checkpointer persiste). El corte siempre empieza en un HumanMessage para
   no dejar respuestas "huérfanas" al inicio del contexto.

## 2026-07-06 — Refactor final: nucleo/ = plataforma pura; cada bot en bots/<nombre>/
Alejandro salió de nucleo/ hacia bots/alejandro/ (nodos, router, tools,
grafo — copiados con `cp` para preservar exactamente la lista de impedimentos
que el dueño amplió a mano). nucleo/grafo.py se dividió: el grafo se fue con
Alejandro y `responder()` quedó en nucleo/ejecucion.py (nombre honesto: ya no
construye grafos, ejecuta cualquiera). `responder(mensaje, thread_id, grafo)`
ahora exige el grafo: nucleo/ no puede tener default de un bot porque NO debe
importar de bots/ (regla de dependencias: nucleo ← bots ← interfaces).
ver_grafo.py acepta el bot como argumento (`poe graph daniela`).

## 2026-07-06 — Exportación a Excel: script del dueño, no tool del bot
`bots/daniela/exportar.py` + `poe exportar`: genera exports/daniela_<fecha>.xlsx
con una hoja por categoría (openpyxl), orden cronológico y encabezados en
negrita. Es un script y NO una tool a propósito: por WhatsApp el bot solo
responde texto — mandar un archivo requeriría hostearlo en URL pública
(anotado como mejora futura). El flujo real: el dueño corre `poe exportar` y
le manda el archivo a Daniela.

## 2026-07-06 — Audio (notas de voz): bloque "media" nativo de Gemini, sin STT aparte
`mensaje_con_audio()` en nucleo/mensajes.py usa el bloque
`{"type": "media", "mime_type", "data"}` — formato VERIFICADO leyendo la
fuente de langchain-google-genai instalada (no adivinado). Registro
`AUDIO = {"gemini"}` + `tiene_audio()` en nucleo/llm: Gemini es el único
proveedor configurado que escucha audio nativo (Claude no acepta audio; el
resto necesitaría transcripción previa, ej. Whisper vía Groq — anotado como
alternativa). El webhook ahora distingue el adjunto por MediaContentType0
(image/* → visión, audio/* → audio, otro → rechazo digno). Las notas de voz
de WhatsApp llegan como audio/ogg.

## 2026-07-06 — Datos de negocio en BD estructurada, NO en la memoria conversacional
Consulta del dueño: ¿consultar registros "buscando en la memoria por fechas"
o contra una BD? Decisión (ya implementada así en Daniela): la memoria del
checkpointer es CONTEXTO conversacional — se recorta (ventana 8 h), es texto
no estructurado y no sirve para agregar/filtrar con exactitud. Los datos de
negocio viven en el almacén SQLite y se consultan vía TOOLS (fuente de
verdad estructurada y exacta). Un endpoint HTTP intermedio (API aparte) solo
se justificaría si la BD fuera remota/compartida con otros sistemas — hoy
sería complejidad gratis.

## 2026-07-06 — Segundo bot: "Daniela" (asistente de ventas telco) en bots/daniela/
Primer bot con dominio real: reemplaza las 4 planillas Excel de Daniela
(ejecutiva de ventas de telecomunicaciones) por conversación de WhatsApp.
Tablas SQLite propias (`datos_daniela.sqlite`): ventas (mct, rut,
conectado/agendado), pendientes (bajas, cambios domicilio, devoluciones),
portabilidades en espera (rut, teléfono, compañía) y homepass. Diseño:
- **Grafo mínimo** (agente puro): START → asistente → loop tools → END.
  Sin router ni ramas: la complejidad vive en las TOOLS y el prompt, no en
  el flujo. Contraste deliberado con Alejandro (didáctico).
- **Temperatura 0.2** (vs 0.7-0.9 de Alejandro): registrar datos exige
  precisión, no creatividad. El prompt prohíbe inventar valores y obliga a
  pedir los datos faltantes antes de registrar.
- **Capas separadas**: almacen.py (solo SQL, testeable sin API) ← tools.py
  (validar/formatear) ← nodos.py (conversación). Whitelist de categorías
  contra inyección SQL vía LLM.
- **Convivencia de 2 bots**: `bots.obtener_bot(nombre)` (imports perezosos),
  `responder(..., grafo=)` opcional (default Alejandro = retrocompatible),
  webhook con 2 endpoints (`/whatsapp` y `/daniela`), memoria SQLite POR BOT
  para que el mismo teléfono hable con ambos sin mezclar historiales.
- Decisión explícita del dueño: son SOLO 2 bots — no generalizar a "N bots".
  Pendiente acordado: mover lo de Alejandro de nucleo/ a bots/alejandro/
  (primero WhatsApp funcionando, después la reorganización).

## 2026-07-06 — Bug real: el router se confundía con el mensaje del propio bot
Al probar `saludo` de punta a punta, un primer mensaje "once" terminó yendo
al nodo `chat` (LLM) en vez de `once` (fijo). Causa: el router miraba
`state["messages"][-1]` a secas, pero al re-evaluarse DESPUÉS de `saludo`,
el último mensaje ya es la respuesta del bot ("Ah, llegaste..."), no lo que
el usuario preguntó. Fix: `_ultimo_mensaje_usuario()` busca hacia atrás el
`HumanMessage` más reciente. Lección: un router "por último mensaje" deja de
ser válido en cuanto hay más de un nodo antes de la decisión — cazado con un
test end-to-end antes de que llegara a WhatsApp real (mismo hábito que los
bugs anteriores: reproducir en aislamiento, no asumir).

## 2026-07-06 — Rename completo: "Daniela" (bot) → "Julieta"
Pedido explícito del dueño: rename COMPLETO, no solo el prompt. Daniela
sigue siendo la ejecutiva de ventas (la dueña del negocio); Julieta es el
nombre del bot que la asiste. `git mv bots/daniela bots/julieta` (preserva
historial), todo el código (`TOOLS_DANIELA`→`TOOLS_JULIETA`,
`DANIELA_SYSTEM` absorbido en el system prompt dinámico de `nodo_asistente`,
imports `bots.daniela`→`bots.julieta`), BD renombradas
(`memoria_daniela.sqlite`→`memoria_julieta.sqlite`,
`datos_daniela.sqlite`→`datos_julieta.sqlite`; eran solo residuos de pruebas
del dueño de la sesión, sin datos reales — se limpiaron para partir frescos),
endpoint `/daniela`→`/julieta`, `poe dev-daniela`→`poe dev-julieta`. Sin
alias de compatibilidad: `obtener_bot('daniela')` ahora falla explícito.

## 2026-07-06 — Nombre por usuario: router_entrada mira el ALMACÉN, no el mensaje
Julieta se presenta y pregunta el nombre la primera vez que un teléfono le
escribe, y lo saluda por su nombre después. Aclaración conceptual que motivó
el diseño: `thread_id` es por CONVERSACIÓN, pero en WhatsApp
`thread_id = From` (el número) → conversación == usuario, así que el
teléfono ya se captura gratis; solo faltaba la tabla `usuarios(telefono →
nombre)`. Diseño:
- `router_entrada(state, config)` en `bots/julieta/grafo.py`: a diferencia
  del router de Alejandro (mira el CONTENIDO del último mensaje), este mira
  el ALMACÉN (`almacen.obtener_nombre(thread_id)`) — otra forma válida de
  arista condicional. Verificado que LangGraph pasa `config` tanto a nodos
  como a funciones de `add_conditional_edges`.
- `nodo_saludo` FIJO (sin LLM, mismo patrón que Alejandro) pide el nombre y
  termina el turno (→ END): la pregunta queda esperando respuesta.
- La tool `guardar_nombre(nombre, config: RunnableConfig)` recibe el
  `thread_id` INYECTADO por LangChain — verificado que el LLM no lo ve ni lo
  decide (`tool.args` no incluye "config" en el schema). Así la tool sabe A
  QUIÉN pertenece el nombre sin que el modelo tenga que inventar o pedir el
  teléfono, que ya se tiene gratis.
- `nodo_asistente(state, config)` arma un system prompt DINÁMICO: si el
  almacén ya tiene nombre para ese teléfono, instruye a saludar por nombre;
  si no, instruye a pedirlo y guardarlo con la tool en cuanto llegue.

## 2026-07-06 — Update y delete de registros, con confirmación obligatoria para eliminar
`almacen.actualizar(categoria, id, campo, valor)` y
`almacen.eliminar(categoria, id)`, ambas con whitelist doble: `CATEGORIAS`
(ya existía) + `CAMPOS_EDITABLES` nuevo (ni `id` ni `creado` son editables —
son identidad/auditoría, no datos de negocio). Devuelven `bool` (existía o
no) en vez de lanzar excepción por id inexistente — un ID que no existe no
es un error de programación, es un caso de uso normal (usuario se equivocó
de número). Decisión del dueño: **eliminar exige confirmación explícita**,
implementada como regla en el system prompt (no en código) — el LLM debe
mostrar el registro, preguntar, y solo llamar `eliminar_registro` tras un
"sí" en el mismo hilo. Actualizar NO requiere confirmación (menos
destructivo) pero debe repetir el cambio hecho. Se optó por regla de prompt
en vez de un paso de código intermedio porque el flujo de confirmación es
inherentemente conversacional (multi-turno) — forzarlo en el grafo hubiera
significado un nodo de espera explícito, más complejo que necesario para el
volumen de uso real (una ejecutiva, no un call center).

## 2026-07-06 — Despliegue en VPS: systemd + uv + Caddy, SIN Docker
Pregunta del dueño: ¿dockerizar es bazooka para esto? Sí. El beneficio
central de Docker (reproducibilidad) ya está cubierto: `uv.lock` congela
versiones exactas, `uv` instala hasta el Python correcto en el servidor, y
las dependencias son wheels puros. El estado son 3 SQLite + un `.env` — no
hay servicios que orquestar. Stack elegido (carpeta `deploy/` con todo):
- **Hetzner** (~€4/mes, ubicación Ashburn por latencia a Chile) + Ubuntu.
- **systemd** (`deploy/bots.service`): mantiene vivo uvicorn, arranca al
  boot, logs con journalctl — el rol de Docker+restart policy, nativo.
- **Caddy** (`deploy/Caddyfile`): reverse proxy con HTTPS automático de
  Let's Encrypt en 2 líneas (los webhooks EXIGEN https válido).
- **DuckDNS** gratis como dominio → URL fija, reemplaza a ngrok.
- **Backups** (`deploy/respaldar.sh` + cron): usa la API .backup de SQLite
  (no `cp`, que con WAL puede copiar estado a medio escribir), 14 días.
- **Deploy diario** (`deploy/actualizar.sh`): git pull + uv sync + restart.
- `.gitattributes` fuerza LF en `deploy/**` (scripts editados en Windows
  con CRLF revientan bash en Linux: "\r: command not found").
Docker se reevalúa si aparece: segundo servicio (Postgres/Redis/workers),
segundo dev, o CI/CD frecuente. Guía completa paso a paso: deploy/GUIA.md.

## 2026-07-13 — Despliegue final: Fly.io (no Hetzner) — decisión del dueño
El dueño desplegó por su cuenta en Fly.io (app `bot-chuleta`, región iad,
Dockerfile generado por Fly Launch + ajustes propios). La guía de Hetzner
(deploy/GUIA.md) queda como referencia histórica. Nota irónica registrada
con cariño: terminamos con Docker igual — pero lo maneja Fly, no nosotros.
Gotcha CRÍTICO detectado en revisión: el disco del contenedor en Fly es
EFÍMERO — sin un volumen montado, cada deploy borra los SQLite (memoria de
bots + datos de Daniela). Fix: `ruta_datos()` en nucleo/config.py (env
DATOS_DIR) + bloque [mounts] preparado en fly.toml (comentado hasta crear
el volumen con `fly volumes create datos --region iad --size 1`).

## 2026-07-13 — Adaptador Meta (WhatsApp Cloud API) en interfaces/meta.py
Rutas GET/POST `/meta/{bot}` montadas como APIRouter en la misma app que
corre Fly. Tres diferencias de contrato vs Twilio, todas manejadas:
1. Handshake GET con hub.verify_token/hub.challenge (config del panel Meta).
2. La respuesta NO viaja en el HTTP response (Twilio: TwiML; Meta: 200
   rápido + POST aparte a la Graph API `/{phone_number_id}/messages` con
   Bearer). Por eso el webhook agenda el trabajo en BackgroundTasks y
   responde al tiro — si el LLM tarda, Meta no reintenta.
3. Firma X-Hub-Signature-256 (HMAC-SHA256 del cuerpo con App Secret)
   validada con compare_digest — la seguridad que en Twilio quedó pendiente
   aquí nace incluida.
Extras del mundo real: dedup por wamid (Meta reintenta webhooks; deque
maxlen=200), eventos de estado (delivered/read) ignorados con 200, media
por media_id (2 pasos con token), mime limpiado de "; codecs=opus".
thread_id = wa_id ("569..." sin prefijo whatsapp:) — canal nuevo, memoria
nueva; no se migran hilos de Twilio. Graph API v21.0 (verificada vigente),
configurable vía META_GRAPH_VERSION. Todo probado offline con TestClient y
el envío mockeado: handshake, firma inválida 403, texto→saludo de Julieta,
dedup, statuses ignorados. Twilio sigue funcionando en paralelo.

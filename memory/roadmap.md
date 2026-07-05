# Roadmap

Actualizar al terminar cada hito (mover a "Hecho" con fecha).

## Siguiente

1. **Imágenes por WhatsApp** — recibir `MediaUrl` de Twilio, descargar la
   imagen y pasarla como bloque multimodal a un proveedor con visión
   (ej. `LLM_PROVIDER=gemini`). Sin OCR. Ver decisión 2026-07-04.
2. **Endurecer webhook para producción** — validar firma `X-Twilio-Signature`.
3. (Opcional, si el bot pasa a "producción") Remitente propio de WhatsApp:
   número + verificación Meta Business → permite foto/nombre de perfil.
   En sandbox NO se puede (número compartido de Twilio).

## Rutina para levantar WhatsApp (recordatorio)

```powershell
uv run poe dev-watch   # terminal 1
ngrok http 8000        # terminal 2 -> URL nueva cada vez
```
Pegar `https://<url-ngrok>/whatsapp` (¡CON /whatsapp!) en Twilio → Sandbox
settings → "When a message comes in" (POST). El join del sandbox expira cada
72h: reenviar `join <código>` al +1 415 523 8886.

## Ideas (sin orden)

- Streaming de respuestas (`grafo.stream()`).
- Tools para Alejandro (`ToolNode`): hora, clima, chistes de API.
- Más campos en el State (humor del jefe, nombre del subordinado) usados en prompts.
- Modelo configurable por proveedor (`GEMINI_MODEL`, etc.) si hace falta.

## Hecho

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

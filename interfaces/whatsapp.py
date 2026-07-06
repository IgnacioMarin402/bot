"""
Interfaz de WHATSAPP (adaptador) — webhook para Twilio.

Flujo de un mensaje:

    Tu WhatsApp -> Twilio -> POST /whatsapp (este servidor) -> grafo -> respuesta

Twilio espera de vuelta un XML llamado TwiML: <Response><Message>texto</Message></Response>.
TwiML soporta VARIOS <Message> en una sola respuesta — Twilio los manda como
burbujas separadas. Por eso `responder()` devuelve una lista (ej. saludo +
respuesta la primera vez que alguien escribe), no un solo texto.

Igual que cli.py, este archivo NO conoce nodos, router ni tools: solo llama a
`responder()`. Y la memoria por persona sale gratis: thread_id = número del
remitente, así el checkpointer guarda una conversación separada para cada
teléfono.

Imágenes (2026-07-06): cuando el mensaje trae una foto, Twilio manda además
`NumMedia` (>0) y `MediaUrl0`/`MediaContentType0`. Esa URL está protegida con
Basic Auth (las credenciales de tu cuenta Twilio) — por eso hace falta
TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN en el .env para poder descargarla.
La descarga es responsabilidad de ESTA interfaz (es un detalle de Twilio);
armar el mensaje multimodal para el LLM es responsabilidad de nucleo/mensajes.py.

Desarrollo:   uv run poe dev-watch      (auto-reload al guardar)
Exponer:      ngrok http 8000           (pegar la URL https en el sandbox de Twilio)

Pendiente para producción real (no sandbox): validar la firma X-Twilio-Signature
para rechazar peticiones que no vengan de Twilio.
"""

import os
from xml.sax.saxutils import escape

import httpx
from fastapi import FastAPI, Form
from fastapi.responses import Response
from langchain_core.messages import HumanMessage

from bots import obtener_bot
from nucleo.ejecucion import responder
from nucleo.llm import tiene_audio, tiene_vision
from nucleo.mensajes import mensaje_con_audio, mensaje_con_imagen

app = FastAPI(title="Bots de WhatsApp — Alejandro y Daniela")


def twiml(textos: list[str]) -> Response:
    """Arma la respuesta TwiML: un <Message> por cada texto (burbujas separadas)."""
    mensajes = "".join(f"<Message>{escape(t)}</Message>" for t in textos)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{mensajes}</Response>'
    return Response(content=xml, media_type="application/xml")


def _descargar_adjunto(url: str) -> bytes:
    """Descarga un adjunto de Twilio (imagen o audio; Basic Auth con tu cuenta)."""
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    respuesta = httpx.get(url, auth=(sid, token), timeout=15)
    respuesta.raise_for_status()
    return respuesta.content


@app.get("/")
def salud():
    """Comprobación rápida de que el servidor vive (ábrelo en el navegador)."""
    return {"ok": True, "bots": ["alejandro (/whatsapp)", "daniela (/daniela)"]}


def _atender(
    nombre_bot: str, Body: str, From: str, NumMedia: str, MediaUrl0: str, MediaContentType0: str
) -> Response:
    """Lógica común de un mensaje entrante, para cualquier bot.

    Cada bot tiene su propio grafo (y su propia memoria SQLite), así que el
    mismo número puede hablar con ambos sin mezclar historiales. El thread_id
    sigue siendo solo el número: la separación la da el checkpointer de cada bot.
    """
    texto = Body.strip()
    hay_adjunto = NumMedia != "0" and MediaUrl0 != ""
    es_imagen = hay_adjunto and MediaContentType0.startswith("image/")
    es_audio = hay_adjunto and MediaContentType0.startswith("audio/")

    if not texto and not hay_adjunto:
        return twiml(["No me llegó texto 😅 ¿me lo reenvías?"])

    if es_imagen and not tiene_vision():
        return twiml(
            [
                "Con este proveedor no puedo ver fotos todavía "
                "(cambia LLM_PROVIDER a uno con visión, ej. gemini) 📵"
            ]
        )
    if es_audio and not tiene_audio():
        return twiml(
            [
                "Con este proveedor no puedo escuchar audios todavía "
                "(cambia LLM_PROVIDER=gemini) 🔇 ¿Me lo escribes?"
            ]
        )
    if hay_adjunto and not es_imagen and not es_audio:
        return twiml(["Ese tipo de archivo no lo manejo 😅 mándame texto, foto o nota de voz."])

    try:
        if es_imagen:
            mensaje = mensaje_con_imagen(texto, _descargar_adjunto(MediaUrl0), MediaContentType0)
        elif es_audio:
            mensaje = mensaje_con_audio(texto, _descargar_adjunto(MediaUrl0), MediaContentType0)
        else:
            mensaje = HumanMessage(content=texto)

        # responder() puede devolver más de un mensaje (ej. saludo + respuesta).
        return twiml(responder(mensaje, thread_id=From, grafo=obtener_bot(nombre_bot)))
    except Exception as error:  # el LLM (o la descarga) puede fallar: avisar digno
        print(f"[whatsapp/{nombre_bot}] error respondiendo a {From}: {error}")
        return twiml(["Se cayó el sistema 🙄 intenta de nuevo en un rato."])


# Los nombres de los parámetros (Body, From, NumMedia...) son los campos
# EXACTOS del formulario que envía Twilio. Son `def` (no `async def`) a
# propósito: FastAPI los ejecuta en un hilo aparte, así el .invoke()
# bloqueante del grafo no congela el servidor.


@app.post("/whatsapp")
def recibir_alejandro(
    Body: str = Form(""),
    From: str = Form("desconocido"),
    NumMedia: str = Form("0"),
    MediaUrl0: str = Form(""),
    MediaContentType0: str = Form(""),
) -> Response:
    """Webhook de Alejandro (el jefe burlón)."""
    return _atender("alejandro", Body, From, NumMedia, MediaUrl0, MediaContentType0)


@app.post("/daniela")
def recibir_daniela(
    Body: str = Form(""),
    From: str = Form("desconocido"),
    NumMedia: str = Form("0"),
    MediaUrl0: str = Form(""),
    MediaContentType0: str = Form(""),
) -> Response:
    """Webhook de la asistente de Daniela (registro de ventas/pendientes/etc.)."""
    return _atender("daniela", Body, From, NumMedia, MediaUrl0, MediaContentType0)

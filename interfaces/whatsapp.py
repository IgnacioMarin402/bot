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

from nucleo.grafo import responder
from nucleo.llm import tiene_vision
from nucleo.mensajes import mensaje_con_imagen

app = FastAPI(title="Alejandro — webhook de WhatsApp")


def twiml(textos: list[str]) -> Response:
    """Arma la respuesta TwiML: un <Message> por cada texto (burbujas separadas)."""
    mensajes = "".join(f"<Message>{escape(t)}</Message>" for t in textos)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{mensajes}</Response>'
    return Response(content=xml, media_type="application/xml")


def _descargar_imagen(url: str) -> bytes:
    """Descarga un adjunto de Twilio (requiere Basic Auth con tu cuenta)."""
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    respuesta = httpx.get(url, auth=(sid, token), timeout=15)
    respuesta.raise_for_status()
    return respuesta.content


@app.get("/")
def salud():
    """Comprobación rápida de que el servidor vive (ábrelo en el navegador)."""
    return {"ok": True, "bot": "Alejandro"}


@app.post("/whatsapp")
def recibir_mensaje(
    Body: str = Form(""),
    From: str = Form("desconocido"),
    NumMedia: str = Form("0"),
    MediaUrl0: str = Form(""),
    MediaContentType0: str = Form(""),
) -> Response:
    """Recibe un mensaje entrante (texto y/o imagen) y responde con el grafo.

    Los nombres de los parámetros (Body, From, NumMedia, MediaUrl0...) son los
    campos EXACTOS del formulario que envía Twilio.

    Nota: es `def` (no `async def`) a propósito: FastAPI la ejecuta en un hilo
    aparte, así el .invoke() bloqueante del grafo no congela el servidor.
    """
    texto = Body.strip()
    hay_imagen = NumMedia != "0" and MediaUrl0 != ""

    if not texto and not hay_imagen:
        return twiml(["Mándame texto po, no te escucho 😅"])

    if hay_imagen and not tiene_vision():
        return twiml(
            [
                "Mándame puro texto, con este proveedor no veo fotos todavía "
                "(cambia LLM_PROVIDER a uno con visión, ej. gemini) 📵"
            ]
        )

    try:
        if hay_imagen:
            imagen_bytes = _descargar_imagen(MediaUrl0)
            mensaje = mensaje_con_imagen(texto, imagen_bytes, MediaContentType0)
        else:
            mensaje = HumanMessage(content=texto)

        # Una conversación por número: el checkpointer separa la memoria solo.
        # responder() puede devolver más de un mensaje (ej. saludo + respuesta).
        return twiml(responder(mensaje, thread_id=From))
    except Exception as error:  # el LLM (o la descarga) puede fallar: avisar digno
        print(f"[whatsapp] error respondiendo a {From}: {error}")
        return twiml(["Se cayó el sistema po 🙄 dale de nuevo en un rato."])

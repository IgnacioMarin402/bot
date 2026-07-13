"""
Interfaz de META (adaptador) — webhook para WhatsApp Cloud API, sin Twilio.

Mismo rol que interfaces/whatsapp.py (Twilio), pero el contrato de Meta es
distinto en TRES cosas fundamentales:

1. VERIFICACIÓN (GET): al configurar el webhook en el panel de Meta, ellos
   mandan un GET con `hub.verify_token` (un string que TÚ inventas y pones
   en ambos lados) y un `hub.challenge`. Si el token coincide, hay que
   devolver el challenge tal cual. Es un handshake de una sola vez.

2. LA RESPUESTA NO VIAJA EN EL HTTP RESPONSE: Twilio esperaba TwiML de
   vuelta; Meta espera un 200 rápido y NADA más. Para responder al usuario
   hay que hacer una llamada aparte a la Graph API
   (POST /{phone_number_id}/messages con Bearer token). Por eso este
   adaptador responde 200 al tiro y procesa en segundo plano
   (BackgroundTasks): si el LLM tarda, Meta no reintenta el webhook.

3. FIRMA X-Hub-Signature-256: Meta firma cada POST con HMAC-SHA256 del
   cuerpo crudo usando el App Secret. Validarla = solo Meta puede invocarte.
   (La protección equivalente en Twilio —X-Twilio-Signature— quedó pendiente;
   aquí nace incluida.)

Extras del mundo real que este adaptador maneja:
- Meta REINTENTA webhooks si no respondes 200 a tiempo → dedup por wamid
  (el id único del mensaje) para no procesar dos veces.
- Meta también manda eventos de estado (entregado/leído) al mismo webhook →
  se ignoran con 200.
- Media (foto/nota de voz): llega como un media_id; hay que pedir la URL a
  la Graph API y descargarla con el token (dos pasos).

Variables de entorno (en Fly: `fly secrets set CLAVE=valor`):
- META_VERIFY_TOKEN  → el string que inventas para el handshake del webhook.
- META_ACCESS_TOKEN  → token de acceso (para producción: de System User).
- META_APP_SECRET    → App Secret para validar firmas (recomendado SIEMPRE).
- META_GRAPH_VERSION → opcional, default v21.0.
"""

import hashlib
import hmac
import json
import os
from collections import deque

import httpx
from fastapi import APIRouter, BackgroundTasks, Request, Response
from langchain_core.messages import HumanMessage

from bots import obtener_bot
from nucleo.ejecucion import responder
from nucleo.llm import tiene_audio, tiene_vision
from nucleo.mensajes import mensaje_con_audio, mensaje_con_imagen

router = APIRouter(prefix="/meta")

BOTS_VALIDOS = ("alejandro", "julieta")

# Meta reintenta webhooks (si un 200 se demora o se pierde). Recordamos los
# últimos wamid procesados para no responder dos veces el mismo mensaje.
# deque con maxlen = memoria acotada; para este volumen sobra.
_wamids_vistos: deque = deque(maxlen=200)


def _version_graph() -> str:
    return os.getenv("META_GRAPH_VERSION", "v21.0")


def _url_graph(recurso: str) -> str:
    return f"https://graph.facebook.com/{_version_graph()}/{recurso}"


def _headers_auth() -> dict:
    return {"Authorization": f"Bearer {os.getenv('META_ACCESS_TOKEN', '')}"}


# ---------------------------------------------------------------------------
# 1. Verificación del webhook (GET) — el handshake de configuración
# ---------------------------------------------------------------------------


@router.get("/{nombre_bot}")
def verificar_webhook(nombre_bot: str, request: Request) -> Response:
    """Responde el challenge de Meta si el verify_token coincide.

    Meta llama esto UNA vez, cuando guardas la URL del webhook en su panel.
    Los parámetros llegan con puntos en el nombre (hub.mode, hub.verify_token,
    hub.challenge), por eso se leen de query_params y no como argumentos.
    """
    params = request.query_params
    token_esperado = os.getenv("META_VERIFY_TOKEN", "")
    if (
        nombre_bot in BOTS_VALIDOS
        and params.get("hub.mode") == "subscribe"
        and token_esperado
        and params.get("hub.verify_token") == token_esperado
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    return Response(status_code=403)


# ---------------------------------------------------------------------------
# 2. Firma: solo Meta puede invocarnos
# ---------------------------------------------------------------------------


def _firma_valida(cuerpo: bytes, firma_header: str) -> bool:
    """Valida X-Hub-Signature-256 = HMAC-SHA256(cuerpo, App Secret).

    Sin META_APP_SECRET configurado no se valida (para el setup inicial),
    pero en producción SIEMPRE debe estar. compare_digest evita timing
    attacks (comparar strings con == filtra información por tiempo).
    """
    secreto = os.getenv("META_APP_SECRET", "")
    if not secreto:
        return True
    esperada = "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, firma_header or "")


# ---------------------------------------------------------------------------
# 3. Mensajes entrantes (POST)
# ---------------------------------------------------------------------------


def _extraer_mensaje(payload: dict) -> tuple[dict | None, str, str]:
    """Saca (mensaje, wa_id_remitente, phone_number_id) del JSON anidado de Meta.

    Devuelve (None, "", "") para eventos que no son mensajes (estados de
    entrega/lectura, etc.) — esos igual deben recibir 200 y se ignoran.
    """
    try:
        valor = payload["entry"][0]["changes"][0]["value"]
        mensaje = valor["messages"][0]
        remitente = mensaje["from"]  # wa_id: "569XXXXXXXX" (sin el prefijo "whatsapp:")
        telefono_id = valor["metadata"]["phone_number_id"]
        return mensaje, remitente, telefono_id
    except (KeyError, IndexError):
        return None, "", ""


@router.post("/{nombre_bot}")
async def recibir_mensaje(nombre_bot: str, request: Request, tareas: BackgroundTasks):
    """Recibe el webhook, valida, y agenda el procesamiento en segundo plano.

    `async def` (a diferencia de los endpoints de Twilio) porque necesitamos
    el CUERPO CRUDO para validar la firma — request.body() es async. El
    trabajo pesado (LLM) NO ocurre aquí: va a BackgroundTasks, que corre la
    función síncrona en un hilo aparte DESPUÉS de devolver el 200.
    """
    if nombre_bot not in BOTS_VALIDOS:
        return Response(status_code=404)

    cuerpo = await request.body()
    if not _firma_valida(cuerpo, request.headers.get("X-Hub-Signature-256", "")):
        return Response(status_code=403)

    payload = json.loads(cuerpo)
    mensaje, remitente, telefono_id = _extraer_mensaje(payload)
    if mensaje is None:
        return {"status": "ignorado"}  # estados de entrega/lectura, etc.

    wamid = mensaje.get("id", "")
    if wamid in _wamids_vistos:
        return {"status": "duplicado"}  # reintento de Meta: ya lo procesamos
    _wamids_vistos.append(wamid)

    tareas.add_task(_procesar, nombre_bot, mensaje, remitente, telefono_id)
    return {"status": "ok"}


def _procesar(nombre_bot: str, mensaje: dict, remitente: str, telefono_id: str) -> None:
    """Arma el mensaje para el grafo, lo invoca y envía las respuestas.

    Corre en segundo plano (hilo aparte): los errores se capturan y se
    intenta avisar al usuario — nunca deben botar el servidor.
    """
    try:
        tipo = mensaje.get("type", "")

        if tipo == "text":
            entrada = HumanMessage(content=mensaje["text"]["body"])
        elif tipo == "image":
            if not tiene_vision():
                _enviar_texto(telefono_id, remitente, "No puedo ver fotos con este proveedor 📵")
                return
            contenido, mime = _descargar_media(mensaje["image"]["id"])
            entrada = mensaje_con_imagen(mensaje["image"].get("caption", ""), contenido, mime)
        elif tipo == "audio":
            if not tiene_audio():
                _enviar_texto(
                    telefono_id, remitente, "No puedo escuchar audios todavía 🔇 ¿me lo escribes?"
                )
                return
            contenido, mime = _descargar_media(mensaje["audio"]["id"])
            entrada = mensaje_con_audio("", contenido, mime)
        else:
            _enviar_texto(
                telefono_id, remitente, "Ese tipo de mensaje no lo manejo 😅 texto, foto o audio."
            )
            return

        # thread_id = wa_id del remitente: misma idea que con Twilio (una
        # conversación por número), formato distinto ("569..." sin prefijo).
        textos = responder(entrada, thread_id=remitente, grafo=obtener_bot(nombre_bot))
        for texto in textos:
            _enviar_texto(telefono_id, remitente, texto)
    except Exception as error:
        print(f"[meta/{nombre_bot}] error respondiendo a {remitente}: {error}")
        try:
            _enviar_texto(telefono_id, remitente, "Se cayó el sistema 🙄 intenta de nuevo.")
        except Exception:
            pass  # si ni el aviso sale, ya quedó logueado arriba


# ---------------------------------------------------------------------------
# 4. Salida: la Graph API (enviar mensajes y descargar media)
# ---------------------------------------------------------------------------


def _enviar_texto(telefono_id: str, para: str, texto: str) -> None:
    """POST a la Graph API. Con Meta, cada respuesta es una llamada aparte."""
    respuesta = httpx.post(
        _url_graph(f"{telefono_id}/messages"),
        headers=_headers_auth(),
        json={"messaging_product": "whatsapp", "to": para, "type": "text", "text": {"body": texto}},
        timeout=15,
    )
    respuesta.raise_for_status()


def _descargar_media(media_id: str) -> tuple[bytes, str]:
    """Dos pasos: pedir la URL temporal del media, luego bajarlo (ambos con token)."""
    info = httpx.get(_url_graph(media_id), headers=_headers_auth(), timeout=15)
    info.raise_for_status()
    datos = info.json()
    archivo = httpx.get(datos["url"], headers=_headers_auth(), timeout=30)
    archivo.raise_for_status()
    # El mime puede venir como "audio/ogg; codecs=opus" — el LLM quiere solo el tipo.
    mime = datos.get("mime_type", "application/octet-stream").split(";")[0].strip()
    return archivo.content, mime

"""
Interfaz de WHATSAPP (adaptador) — webhook para Twilio.

Flujo de un mensaje:

    Tu WhatsApp -> Twilio -> POST /whatsapp (este servidor) -> grafo -> respuesta

Twilio espera de vuelta un XML llamado TwiML: <Response><Message>texto</Message></Response>.
Eso es TODO el contrato.

Igual que cli.py, este archivo NO conoce nodos ni router: solo usa el grafo.
Y la memoria por persona sale gratis: thread_id = número del remitente, así el
checkpointer guarda una conversación separada para cada teléfono.

Desarrollo:   uv run poe dev-watch      (auto-reload al guardar)
Exponer:      ngrok http 8000           (pegar la URL https en el sandbox de Twilio)

Pendiente para producción real (no sandbox): validar la firma X-Twilio-Signature
para rechazar peticiones que no vengan de Twilio.
"""

from xml.sax.saxutils import escape

from fastapi import FastAPI, Form
from fastapi.responses import Response
from langchain_core.messages import HumanMessage

from nucleo.grafo import obtener_grafo

app = FastAPI(title="Alejandro — webhook de WhatsApp")


def twiml(texto: str) -> Response:
    """Arma la respuesta TwiML (el XML que Twilio espera del webhook)."""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{escape(texto)}</Message></Response>"
    )
    return Response(content=xml, media_type="application/xml")


@app.get("/")
def salud():
    """Comprobación rápida de que el servidor vive (ábrelo en el navegador)."""
    return {"ok": True, "bot": "Alejandro"}


@app.post("/whatsapp")
def recibir_mensaje(Body: str = Form(""), From: str = Form("desconocido")) -> Response:
    """Recibe un mensaje entrante y responde con el grafo.

    Los nombres de los parámetros (Body, From) son los campos EXACTOS del
    formulario que envía Twilio.

    Nota: es `def` (no `async def`) a propósito: FastAPI la ejecuta en un hilo
    aparte, así el .invoke() bloqueante del grafo no congela el servidor.
    """
    texto = Body.strip()
    if not texto:
        return twiml("Mándame texto po, no te escucho 😅")

    # Una conversación por número: el checkpointer separa la memoria solo.
    config = {"configurable": {"thread_id": From}}
    try:
        resultado = obtener_grafo().invoke(
            {"messages": [HumanMessage(content=texto)]},
            config=config,
        )
        return twiml(resultado["messages"][-1].text)
    except Exception as error:  # el LLM puede fallar (límites, red): avisar digno
        print(f"[whatsapp] error respondiendo a {From}: {error}")
        return twiml("Se cayó el sistema po 🙄 dale de nuevo en un rato.")

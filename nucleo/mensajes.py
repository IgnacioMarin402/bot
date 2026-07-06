"""
Construcción de mensajes MULTIMODALES (texto + imagen) para el LLM.

Vive en `nucleo/` y no en `interfaces/` a propósito: el formato con el que se
le habla al modelo (bloques de contenido de LangChain) es un detalle de la
lógica del bot, no de WhatsApp. Si mañana se agrega Telegram o una interfaz
web, reutilizan esta misma función — solo cambia CÓMO se consigue la imagen
(eso sí es responsabilidad de cada interfaz).
"""

import base64

from langchain_core.messages import HumanMessage


def mensaje_con_imagen(texto: str, imagen_bytes: bytes, mime_type: str) -> HumanMessage:
    """Arma un HumanMessage con texto + una imagen en base64.

    El formato de bloques ("image_url" con data URI) es el estándar que
    popularizó OpenAI y que la mayoría de integraciones de LangChain aceptan
    (incluye OpenRouter, por ser compatible con la API de OpenAI).

    Requiere un proveedor con VISIÓN (ver nucleo/llm/proveedores.py -> VISION).
    Con un proveedor sin visión, el modelo puede ignorar la imagen o fallar
    — por eso el llamador debe chequear antes con `tiene_vision()`.
    """
    b64 = base64.b64encode(imagen_bytes).decode("utf-8")
    return HumanMessage(
        content=[
            {"type": "text", "text": texto or "¿Qué ves en esta imagen?"},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
        ]
    )


def mensaje_con_audio(texto: str, audio_bytes: bytes, mime_type: str) -> HumanMessage:
    """Arma un HumanMessage con texto + un audio en base64 (ej. nota de voz).

    Usa el bloque "media" (formato de langchain-google-genai, verificado en
    la fuente de la librería): Gemini "escucha" el audio nativo — transcribe
    e interpreta sin OCR/STT aparte. Es el ÚNICO de nuestros proveedores con
    audio de entrada; el llamador debe chequear antes con `tiene_audio()`.
    Las notas de voz de WhatsApp llegan como audio/ogg.
    """
    b64 = base64.b64encode(audio_bytes).decode("utf-8")
    return HumanMessage(
        content=[
            {"type": "text", "text": texto or "Escucha este audio y responde a lo que dice."},
            {"type": "media", "mime_type": mime_type, "data": b64},
        ]
    )

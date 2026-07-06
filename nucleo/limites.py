"""
PROTECCIONES contra abuso: rate limit, tope de largo y ventana de jornada.

Principio (ver decisión 2026-07-06): rechazar lo más BARATO posible, lo más
TEMPRANO posible. Un `if` acá cuesta nanosegundos; una llamada al LLM cuesta
plata y segundos. Por eso estas protecciones se aplican en `responder()`
ANTES de invocar el grafo — y sus rechazos NO se guardan en el historial
(lección de la contaminación de contexto: basura que entra, basura que el
LLM imita después).

Las tres protecciones:
1. Rate limit por thread_id  -> un usuario no puede quemar la cuota de API.
2. Tope de largo de mensaje  -> nadie manda "la biblia" (entrada = tokens = plata).
3. Ventana de jornada (8 h)  -> el LLM solo VE los mensajes recientes, aunque
   la memoria completa siga guardada en SQLite. Sin esto, el costo por turno
   CRECE para siempre: el historial completo se re-envía en cada mensaje.

Nota de producción: el rate limit vive en memoria del proceso (se resetea al
reiniciar y no se comparte entre procesos). Para múltiples workers/servidores
se usaría Redis — innecesario aquí (un solo proceso uvicorn).
"""

import threading
import time
from collections import defaultdict, deque

from langchain_core.messages import BaseMessage, HumanMessage

# --- Configuración -----------------------------------------------------------

# 10/min = 1 mensaje cada 6 segundos sostenido: holgado para un humano
# escribiendo por WhatsApp, asfixiante para un script de spam.
LIMITE_MENSAJES_POR_MINUTO = 10
VENTANA_RATE_LIMIT_SEGUNDOS = 60

# Más de esto ni se mira: la entrada larga se cobra en tokens.
LARGO_MAXIMO_MENSAJE = 10_000

# "La jornada laboral de Alejandro": al LLM solo se le envían los mensajes
# de las últimas 8 horas. La memoria completa sigue viva en memoria.sqlite.
VENTANA_JORNADA_HORAS = 8

# --- 1. Rate limit por usuario (ventana deslizante) ---------------------------

# thread_id -> timestamps de los mensajes ACEPTADOS en la ventana.
# El Lock existe porque FastAPI atiende cada request en un hilo distinto.
_llamadas_por_usuario: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def permitir_mensaje(thread_id: str, ahora: float | None = None) -> bool:
    """True si este usuario aún tiene cupo en la ventana; registra la llamada.

    Ventana DESLIZANTE (no "por minuto de reloj"): se descartan los timestamps
    más viejos que 60 s y se cuenta lo que queda. `ahora` es inyectable solo
    para poder testear sin esperar minutos reales.
    """
    ahora = time.time() if ahora is None else ahora
    with _lock:
        llamadas = _llamadas_por_usuario[thread_id]
        while llamadas and llamadas[0] <= ahora - VENTANA_RATE_LIMIT_SEGUNDOS:
            llamadas.popleft()
        if len(llamadas) >= LIMITE_MENSAJES_POR_MINUTO:
            return False
        llamadas.append(ahora)
        return True


# --- 2. Tope de largo ---------------------------------------------------------


def mensaje_demasiado_largo(mensaje: BaseMessage) -> bool:
    """True si el texto del mensaje excede el tope (las imágenes no cuentan aquí)."""
    return len(mensaje.text) > LARGO_MAXIMO_MENSAJE


# --- 3. Ventana de jornada (recorte de historial hacia el LLM) ----------------


def marcar_tiempo(mensaje: BaseMessage, ahora: float | None = None) -> None:
    """Estampa la hora de llegada en el mensaje (los mensajes de LangChain no
    traen timestamp propio). Va en `additional_kwargs`, que el checkpointer
    serializa y persiste — así la marca sobrevive reinicios del bot."""
    mensaje.additional_kwargs["marca_tiempo"] = time.time() if ahora is None else ahora


def recortar_jornada(mensajes: list, ahora: float | None = None) -> list:
    """Devuelve solo los mensajes desde el PRIMER mensaje del usuario que cae
    dentro de la jornada (últimas 8 h). Todo lo anterior no se le envía al LLM.

    Se corta en un HumanMessage (no en cualquier mensaje) para que la ventana
    empiece siempre en un turno del usuario: así nunca queda un AIMessage o
    ToolMessage "huérfano" al inicio, sin la pregunta que lo causó.

    Mensajes sin marca (anteriores a esta feature) se tratan como viejos.
    Si ningún mensaje del usuario cae en la ventana (no debería pasar: el
    mensaje entrante siempre se estampa en responder()), se devuelve la lista
    intacta — defensivo, mejor mandar de más que romper el turno.
    """
    ahora = time.time() if ahora is None else ahora
    limite = ahora - VENTANA_JORNADA_HORAS * 3600
    for indice, mensaje in enumerate(mensajes):
        if isinstance(mensaje, HumanMessage):
            marca = mensaje.additional_kwargs.get("marca_tiempo")
            if marca is not None and marca >= limite:
                return mensajes[indice:]
    return mensajes

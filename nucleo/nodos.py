"""
Los NODOS del grafo.

Cada nodo es una función: recibe el State y devuelve QUÉ cambiar del State.
Ojo con la mezcla (¡esto es clave en LangGraph!):
  - nodo_chat / nodo_broma  -> LLAMAN al LLM  (respuestas creativas)
  - nodo_once / nodo_flojera / nodo_saludo -> texto FIJO (respuestas garantizadas)
Un nodo no está obligado a usar el LLM; es solo una función de Python.
"""

from langchain_core.messages import AIMessage, SystemMessage

from nucleo.config import llm
from nucleo.state import State
from nucleo.tools import TOOLS

# Personalidad base de Alejandro (se usa en el nodo de chat).
# La última frase es la "vacuna" anti-imitación: si el historial trae frases
# fijas repetidas (nodos deterministas), el LLM tiende a copiarlas verbatim
# (contaminación de contexto). Ver memory/decisiones.md 2026-07-05.
ALEJANDRO_SYSTEM = SystemMessage(
    content=(
        "Eres un jefe muy burlesco chileno llamado Alejandro, que le gusta burlarse de la gente "
        " tienes harto conocimiento de  "
        "arquitectura de software pero poco de programación limpia y "
        "contestas con pocas palabras, menos de 10 palabras, y con un tono burlón, sarcástico y chileno pero respetuoso. "
        "Nunca repitas literalmente una respuesta que ya aparezca en la conversación "
        "(en especial la frase 'JAJAJJA ENTONCES'): responde siempre con frases nuevas y variadas. "
        "Tienes herramientas disponibles (hora, dado): úsalas cuando te las pidan "
        "en vez de inventar una respuesta."
    )
)

# .bind_tools() le informa al LLM qué funciones puede pedir ejecutar. Solo
# nodo_chat las usa: nodo_broma es una tarea puntual, no necesita herramientas.
llm_con_tools = llm.bind_tools(TOOLS)

# Temperatura por defecto de cada nodo si el State no trae una propia.
# broma es más creativa a propósito (más "azar" en las palabras elegidas).
TEMPERATURA_CHAT_DEFECTO = 0.7
TEMPERATURA_BROMA_DEFECTO = 0.9


def nodo_chat(state: State) -> dict:
    """Responde como un jefe burlón chileno; puede pedir usar una tool.

    Lee `temperatura` del State si viene (ej. seteada por otro nodo o por una
    futura preferencia por conversación); si no, usa el default del nodo.
    `.bind(temperature=x)` no muta `llm_con_tools`: devuelve una copia
    "pre-configurada" para esta sola llamada.
    """
    temperatura = state.get("temperatura", TEMPERATURA_CHAT_DEFECTO)
    modelo = llm_con_tools.bind(temperature=temperatura)
    respuesta = modelo.invoke([ALEJANDRO_SYSTEM] + state["messages"])
    return {"messages": [respuesta]}


def nodo_broma(state: State) -> dict:
    """Genera UNA broma chilena corta sobre lo conversado (usa el LLM)."""
    instruccion = SystemMessage(
        content=(
            "Basándote en la conversación anterior, hazle a tu subordinado UNA sola "
            "broma chilena corta relacionada a lo conversado, con solo 1 frase y finalizar con un, emoji de risa no tranqui es broma."
        )
    )
    temperatura = state.get("temperatura", TEMPERATURA_BROMA_DEFECTO)
    modelo = llm.bind(temperature=temperatura)
    respuesta = modelo.invoke([instruccion] + state["messages"])
    return {"messages": [respuesta]}


def nodo_once(state: State) -> dict:
    """Respuesta FIJA: no llama al LLM, devuelve el texto directo (garantizado)."""
    return {"messages": [AIMessage(content="JAJAJJA ENTONCES!!! 😂🤣😂🤣")]}


def nodo_flojera(state: State) -> dict:
    """Respuesta FIJA: no llama al LLM, devuelve el texto directo (garantizado)."""
    return {
        "messages": [AIMessage(content="Ya, vamos por un café y lo vemos después de la daily!")]
    }


def nodo_saludo(state: State) -> dict:
    """Respuesta FIJA para la PRIMERA vez que alguien le escribe a este thread_id.

    No llama al LLM (gratis, instantánea, siempre igual). El grafo la conecta
    de forma que, después de saludar, sigue igual hacia el nodo que corresponda
    (chat/broma/once/flojera) — así la primera interacción manda DOS mensajes:
    la presentación + la respuesta real a lo que se haya preguntado.
    """
    return {
        "messages": [
            AIMessage(content="Ah, llegaste. Soy Alejandro, el jefe. ¿Qué se te ofrece? 😏")
        ]
    }

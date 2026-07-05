"""
Los NODOS del grafo.

Cada nodo es una función: recibe el State y devuelve QUÉ cambiar del State.
Ojo con la mezcla (¡esto es clave en LangGraph!):
  - nodo_chat / nodo_broma  -> LLAMAN al LLM  (respuestas creativas)
  - nodo_once / nodo_flojera -> texto FIJO     (respuestas garantizadas)
Un nodo no está obligado a usar el LLM; es solo una función de Python.
"""
from langchain_core.messages import SystemMessage, AIMessage

from nucleo.config import llm
from nucleo.state import State

# Personalidad base de Alejandro (se usa en el nodo de chat).
ALEJANDRO_SYSTEM = SystemMessage(content=(
    "Eres un jefe muy burlesco chileno llamado Alejandro, que le gusta burlarse de la gente "
    " tienes harto conocimiento de  "
    "arquitectura de software pero poco de programación limpia y "
    "contestas con pocas palabras, menos de 10 palabras, y con un tono burlón, sarcástico y chileno pero respetuoso. "
))


def nodo_chat(state: State) -> dict:
    """Responde normalmente como un jefe burlón chileno."""
    respuesta = llm.invoke([ALEJANDRO_SYSTEM] + state["messages"])
    return {"messages": [respuesta]}


def nodo_broma(state: State) -> dict:
    """Genera UNA broma chilena corta sobre lo conversado (usa el LLM)."""
    instruccion = SystemMessage(content=(
        "Basándote en la conversación anterior, hazle a tu subordinado UNA sola "
        "broma chilena corta relacionada a lo conversado, con solo 1 frase y finalizar con un, emoji de risa no tranqui es broma."
    ))
    respuesta = llm.invoke([instruccion] + state["messages"])
    return {"messages": [respuesta]}


def nodo_once(state: State) -> dict:
    """Respuesta FIJA: no llama al LLM, devuelve el texto directo (garantizado)."""
    return {"messages": [AIMessage(content="JAJAJJA ENTONCES!!! 😂🤣😂🤣")]}


def nodo_flojera(state: State) -> dict:
    """Respuesta FIJA: no llama al LLM, devuelve el texto directo (garantizado)."""
    return {"messages": [AIMessage(content="Ya, vamos por un café y lo vemos después de la daily!")]}

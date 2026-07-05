"""
La ARISTA CONDICIONAL (el "if" del grafo).

`router` mira el último mensaje del usuario y devuelve el NOMBRE del nodo
al que hay que ir. LangGraph usa ese nombre para elegir la rama.
"""
from nucleo.state import State

palabras_once = ("11", "once")
palabras_broma = ("urgente", "por favor", "necesito")
palabras_clave = palabras_once + palabras_broma


def router(state: State) -> str:
    ultimo = state["messages"][-1].content.lower()
    if len(ultimo) > 30 and not any(palabra in ultimo for palabra in palabras_clave):
        return "flojera"
    elif any(palabra in ultimo for palabra in palabras_broma):
        return "broma"
    elif any(palabra in ultimo for palabra in palabras_once):
        return "once"
    return "chat"

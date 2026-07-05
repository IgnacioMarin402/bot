"""
La ARISTA CONDICIONAL (el "if" del grafo).

`router` mira el último mensaje del usuario y devuelve el NOMBRE del nodo
al que hay que ir. LangGraph usa ese nombre para elegir la rama.

Lección aprendida (bug real, 2026-07-05): buscar subcadenas con `in` hace
que "once" matchee dentro de "entONCEs". Hay que comparar PALABRAS completas:
`\b` en regex significa "frontera de palabra" (inicio/fin de una palabra).
"""

import re

from nucleo.state import State

palabras_once = ("11", "once")
palabras_broma = ("urgente", "por favor", "necesito")
palabras_clave = palabras_once + palabras_broma


def _contiene_palabra(texto: str, palabra: str) -> bool:
    """True si `palabra` aparece COMPLETA en el texto (no como pedazo de otra).

    "once" -> matchea en "tomamos once?" pero NO en "entonces".
    Funciona también con frases ("por favor") y números ("11" no matchea "2011").
    """
    return re.search(rf"\b{re.escape(palabra)}\b", texto) is not None


def router(state: State) -> str:
    ultimo = state["messages"][-1].content.lower()
    if len(ultimo) > 30 and not any(_contiene_palabra(ultimo, p) for p in palabras_clave):
        return "flojera"
    elif any(_contiene_palabra(ultimo, p) for p in palabras_broma):
        return "broma"
    elif any(_contiene_palabra(ultimo, p) for p in palabras_once):
        return "once"
    return "chat"

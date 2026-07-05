"""
El State: los datos que fluyen por el grafo.

`add_messages` es un "reducer": en vez de reemplazar la lista de mensajes,
AGREGA los nuevos a los que ya había. Así el historial se acumula solo.

`temperatura` (2026-07-06) es un ejemplo de OTRA cosa que puede viajar en el
State además de mensajes: no tiene reducer especial, así que LangGraph usa el
default ("el último valor que se escriba gana"). Es `NotRequired` porque no
todo mensaje la trae — los nodos la leen con `state.get("temperatura")` y
usan un valor por defecto si no está. Otros candidatos para el State de este
proyecto: nombre del usuario, idioma preferido, contador de mensajes, humor
del jefe. Cualquier dato que un nodo necesite y que no viva ya en el mensaje
es candidato a campo del State.
"""

from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import NotRequired, TypedDict


class State(TypedDict):
    messages: Annotated[list, add_messages]
    temperatura: NotRequired[float]

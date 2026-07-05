"""
El State: los datos que fluyen por el grafo.

`add_messages` es un "reducer": en vez de reemplazar la lista de mensajes,
AGREGA los nuevos a los que ya había. Así el historial se acumula solo.
"""

from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class State(TypedDict):
    messages: Annotated[list, add_messages]

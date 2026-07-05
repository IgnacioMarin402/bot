"""
Construcción del GRAFO: une State + nodos + router + memoria.

Este módulo expone `grafo`, el objeto ya compilado y listo para usar.
Las interfaces (CLI, WhatsApp) solo importan esto:

    from nucleo.grafo import grafo
"""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from nucleo.state import State
from nucleo.nodos import nodo_chat, nodo_broma, nodo_once, nodo_flojera
from nucleo.router import router


def construir_grafo():
    builder = StateGraph(State)

    # 1. Registramos los nodos.
    builder.add_node("chat", nodo_chat)
    builder.add_node("broma", nodo_broma)
    builder.add_node("once", nodo_once)
    builder.add_node("flojera", nodo_flojera)

    # 2. Desde START, el router decide a qué nodo ir (arista condicional).
    builder.add_conditional_edges(
        START,
        router,
        {"chat": "chat", "once": "once", "broma": "broma", "flojera": "flojera"},
    )

    # 3. Todos los nodos terminan el turno.
    builder.add_edge("chat", END)
    builder.add_edge("once", END)
    builder.add_edge("broma", END)
    builder.add_edge("flojera", END)

    # 4. Checkpointer: memoria en RAM (se pierde al cerrar). Para memoria
    #    persistente en disco, cambiar por SqliteSaver.
    memoria = MemorySaver()
    return builder.compile(checkpointer=memoria)


# El grafo ya compilado, listo para que cualquier interfaz lo use.
grafo = construir_grafo()

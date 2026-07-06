"""
El GRAFO de Alejandro: une State + nodos + router + memoria.

Es el grafo "didáctico" del proyecto: router por reglas (once/broma/flojera),
saludo de primera vez, y un nodo chat agéntico con loop de tools. Comparar
con bots/daniela/grafo.py (agente puro, sin router) para ver los dos extremos.

Memoria propia: memoria.sqlite en la raíz del proyecto (separada de la de
Daniela para que el mismo teléfono hable con ambos sin mezclar historiales).
"""

import sqlite3
from functools import lru_cache
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from bots.alejandro.nodos import nodo_broma, nodo_chat, nodo_flojera, nodo_once, nodo_saludo
from bots.alejandro.router import router, router_entrada
from bots.alejandro.tools import TOOLS
from nucleo.state import State

RUTA_DB = Path(__file__).resolve().parents[2] / "memoria.sqlite"


def construir_grafo():
    builder = StateGraph(State)

    # 1. Registramos los nodos.
    builder.add_node("saludo", nodo_saludo)
    builder.add_node("chat", nodo_chat)
    builder.add_node("broma", nodo_broma)
    builder.add_node("once", nodo_once)
    builder.add_node("flojera", nodo_flojera)
    # ToolNode ejecuta la(s) tool(s) que el LLM haya pedido en su último mensaje.
    builder.add_node("tools", ToolNode(TOOLS))

    # 2. Desde START, `router_entrada` intercepta el PRIMER mensaje de cada
    #    conversación y lo manda a "saludo"; el resto de las veces delega en
    #    el `router` normal (once/broma/flojera/chat).
    builder.add_conditional_edges(
        START,
        router_entrada,
        {
            "saludo": "saludo",
            "chat": "chat",
            "once": "once",
            "broma": "broma",
            "flojera": "flojera",
        },
    )

    # 2b. Tras saludar, se vuelve a evaluar el MISMO router para decidir la
    #     respuesta real — así la primera interacción deja DOS mensajes en el
    #     historial: la presentación + la respuesta a lo preguntado.
    builder.add_conditional_edges(
        "saludo",
        router,
        {"chat": "chat", "once": "once", "broma": "broma", "flojera": "flojera"},
    )

    # 3. "chat" es especial: en vez de ir siempre a END, `tools_condition` mira
    #    si el LLM pidió usar una tool. Si sí -> nodo "tools"; si no -> END.
    #    Tras ejecutar la tool, se vuelve a "chat" para que el LLM redacte la
    #    respuesta final usando el resultado (el clásico loop ReAct).
    builder.add_conditional_edges("chat", tools_condition)
    builder.add_edge("tools", "chat")

    # Los demás nodos son de una sola pasada: terminan el turno directo.
    builder.add_edge("once", END)
    builder.add_edge("broma", END)
    builder.add_edge("flojera", END)

    # 4. Checkpointer PERSISTENTE en SQLite. check_same_thread=False porque
    #    el servidor web (FastAPI) atiende cada request en un hilo distinto.
    conexion = sqlite3.connect(RUTA_DB, check_same_thread=False)
    return builder.compile(checkpointer=SqliteSaver(conexion))


@lru_cache(maxsize=1)
def obtener_grafo():
    """Singleton perezoso: se construye la primera vez que alguien lo pide."""
    return construir_grafo()

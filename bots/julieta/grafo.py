"""
El GRAFO de Julieta: agente puro (asistente + tools) con una arista de
entrada que decide si hace falta saludar primero.

    START -> ¿ya sé tu nombre? -> saludo -> END
                                -> asistente -> ¿pidió tool? -> tools -> asistente -> ... -> END

Comparado con Alejandro (router de personalidad + 5 nodos), este grafo casi
no tiene ramas: la única decisión de `router_entrada` es "¿el almacén ya
tiene un nombre para este teléfono?" — no mira el CONTENIDO del mensaje como
el router de Alejandro, mira el ALMACÉN. La complejidad del bot vive en las
TOOLS y el prompt, no en el flujo.

Memoria propia: memoria_julieta.sqlite (separada de la de Alejandro para que
el mismo número de teléfono pueda hablar con ambos bots sin mezclar historiales).
"""

import sqlite3
from functools import lru_cache
from pathlib import Path

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from bots.julieta import almacen
from bots.julieta.nodos import nodo_asistente, nodo_saludo
from bots.julieta.tools import TOOLS_JULIETA
from nucleo.state import State

RUTA_DB = Path(__file__).resolve().parents[2] / "memoria_julieta.sqlite"


def router_entrada(state: State, config: RunnableConfig) -> str:
    """Arista desde START: manda a "saludo" solo en el primer mensaje de un
    teléfono que TODAVÍA no tiene nombre guardado. El resto de las veces
    (incluida la respuesta al saludo, que ya trae el nombre) va directo al
    asistente.

    Nota: a diferencia del router de Alejandro (que mira el CONTENIDO del
    mensaje), este mira el ALMACÉN — otra forma válida de decidir una arista
    condicional; LangGraph le pasa `config` a la función igual que a un nodo.
    """
    telefono = config["configurable"]["thread_id"]
    es_primer_mensaje = len(state["messages"]) <= 1
    if es_primer_mensaje and almacen.obtener_nombre(telefono) is None:
        return "saludo"
    return "asistente"


def construir_grafo():
    builder = StateGraph(State)

    builder.add_node("saludo", nodo_saludo)
    builder.add_node("asistente", nodo_asistente)
    builder.add_node("tools", ToolNode(TOOLS_JULIETA))

    builder.add_conditional_edges(
        START, router_entrada, {"saludo": "saludo", "asistente": "asistente"}
    )
    # El saludo termina el turno: la pregunta por el nombre queda esperando
    # respuesta (no se sigue directo al asistente en la misma pasada).
    builder.add_edge("saludo", END)

    # El loop agente: si el LLM pidió una tool -> ejecutarla y volver;
    # si respondió texto -> END. (tools_condition, prebuilt de LangGraph.)
    builder.add_conditional_edges("asistente", tools_condition)
    builder.add_edge("tools", "asistente")

    conexion = sqlite3.connect(RUTA_DB, check_same_thread=False)
    return builder.compile(checkpointer=SqliteSaver(conexion))


@lru_cache(maxsize=1)
def obtener_grafo():
    """Singleton perezoso: se construye la primera vez que alguien lo pide."""
    return construir_grafo()

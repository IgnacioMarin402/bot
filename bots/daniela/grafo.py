"""
El GRAFO de Daniela: el patrón agente puro (el más simple posible con tools).

    START -> asistente -> ¿pidió tool? -> tools -> asistente -> ... -> END

Comparado con Alejandro (router + 5 nodos + saludo), este grafo es mínimo:
un nodo LLM y su loop de herramientas. La complejidad del bot está en las
TOOLS y el prompt, no en el flujo — elección deliberada según el dominio.

Memoria propia: memoria_daniela.sqlite (separada de la de Alejandro para que
el mismo número de teléfono pueda hablar con ambos bots sin mezclar historiales).
"""

import sqlite3
from functools import lru_cache
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from bots.daniela.nodos import nodo_asistente
from bots.daniela.tools import TOOLS_DANIELA
from nucleo.state import State

RUTA_DB = Path(__file__).resolve().parents[2] / "memoria_daniela.sqlite"


def construir_grafo():
    builder = StateGraph(State)

    builder.add_node("asistente", nodo_asistente)
    builder.add_node("tools", ToolNode(TOOLS_DANIELA))

    # Sin router: todo mensaje entra directo al asistente (arista FIJA).
    builder.add_edge(START, "asistente")

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

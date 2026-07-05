"""
Construcción del GRAFO: une State + nodos + router + memoria.

Este módulo expone `obtener_grafo()`. Las interfaces (CLI, WhatsApp) hacen:

    from nucleo.grafo import obtener_grafo
    grafo = obtener_grafo()

¿Por qué una función y no un objeto ya construido? Para que IMPORTAR este
módulo no tenga efectos secundarios (crear memoria.sqlite, abrir conexiones).
El grafo se construye recién cuando alguien lo pide — y una sola vez, porque
lru_cache lo convierte en singleton perezoso.
"""

import sqlite3
from functools import lru_cache
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from nucleo.nodos import nodo_broma, nodo_chat, nodo_flojera, nodo_once
from nucleo.router import router
from nucleo.state import State

# Archivo donde vive la memoria. Se crea solo al lado del proyecto.
RUTA_DB = Path(__file__).resolve().parent.parent / "memoria.sqlite"


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

    # 4. Checkpointer PERSISTENTE: guarda el estado en un archivo SQLite, así
    #    Alejandro recuerda cada conversación (por thread_id) aunque cierres.
    #    check_same_thread=False -> la conexión podrá usarse desde el servidor
    #    web (WhatsApp) más adelante, no solo desde el hilo principal.
    conexion = sqlite3.connect(RUTA_DB, check_same_thread=False)
    memoria = SqliteSaver(conexion)
    return builder.compile(checkpointer=memoria)


# Singleton perezoso: la PRIMERA llamada construye el grafo (y ahí recién se
# crea/abre memoria.sqlite); las siguientes devuelven el mismo objeto cacheado.
@lru_cache(maxsize=1)
def obtener_grafo():
    return construir_grafo()

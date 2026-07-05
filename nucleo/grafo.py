"""
Construcción del GRAFO: une State + nodos + router + memoria.

Este módulo expone `obtener_grafo()` y `responder()`. Las interfaces (CLI,
WhatsApp) usan sobre todo `responder()`:

    from nucleo.grafo import responder
    textos = responder(HumanMessage(content="hola"), thread_id="...")

¿Por qué una función y no un objeto ya construido? Para que IMPORTAR este
módulo no tenga efectos secundarios (crear memoria.sqlite, abrir conexiones).
El grafo se construye recién cuando alguien lo pide — y una sola vez, porque
lru_cache lo convierte en singleton perezoso.
"""

import sqlite3
from functools import lru_cache
from pathlib import Path

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from nucleo.nodos import nodo_broma, nodo_chat, nodo_flojera, nodo_once, nodo_saludo
from nucleo.router import router, router_entrada
from nucleo.state import State
from nucleo.tools import TOOLS

# Archivo donde vive la memoria. Se crea solo al lado del proyecto.
RUTA_DB = Path(__file__).resolve().parent.parent / "memoria.sqlite"


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


def responder(mensaje: BaseMessage, thread_id: str) -> list[str]:
    """Invoca el grafo y devuelve los TEXTOS nuevos para mostrarle al usuario.

    Por qué puede ser más de uno: un turno puede agregar varios mensajes al
    historial (ej. saludo + respuesta la primera vez). Por qué hay que
    filtrar: durante el loop de tools también se agregan un AIMessage sin
    texto (solo con tool_calls) y un ToolMessage con el resultado crudo —
    ninguno de los dos es para mostrar, son pasos internos del LLM.

    Se centraliza acá (y no en cada interfaz) para que CLI y WhatsApp no
    dupliquen esta lógica — ambas solo necesitan "mandale esto, dime qué
    responder", sin saber nada de nodos, tools ni cómo se arma el historial.
    """
    grafo = obtener_grafo()
    config = {"configurable": {"thread_id": thread_id}}

    previos = grafo.get_state(config).values.get("messages", [])
    resultado = grafo.invoke({"messages": [mensaje]}, config=config)
    nuevos = resultado["messages"][len(previos) :]

    return [m.text for m in nuevos if isinstance(m, AIMessage) and m.text]

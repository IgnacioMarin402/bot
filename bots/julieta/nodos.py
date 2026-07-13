"""
Los NODOS de Julieta: un saludo fijo (primera vez) + un asistente con tools.

Contraste didáctico con Alejandro: este bot no necesita router de personalidad
— casi todo pasa por un agente con herramientas, porque su trabajo es uno
solo: entender el mensaje, extraer los datos y registrarlos/consultarlos. La
única rama es "¿ya sé tu nombre?", y ni siquiera es un router de contenido:
la decide `router_entrada` en grafo.py mirando el almacén, no el mensaje.
"""

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from bots.julieta import almacen
from bots.julieta.tools import TOOLS_JULIETA
from nucleo.config import llm
from nucleo.limites import recortar_jornada
from nucleo.state import State

# Precisión sobre creatividad: para registrar datos, temperatura BAJA.
# (Alejandro usa 0.7-0.9 porque improvisa chistes; acá inventar es un bug.)
TEMPERATURA_DEFECTO = 0.2

llm_con_tools = llm.bind_tools(TOOLS_JULIETA)


def nodo_saludo(state: State) -> dict:
    """Respuesta FIJA para quien le escribe a Julieta por primera vez.

    No llama al LLM (gratis, instantánea, siempre igual — mismo patrón que
    Alejandro). Termina el turno (el grafo la manda a END): la pregunta
    queda esperando el nombre como respuesta. Si el primer mensaje ya traía
    una tarea (ej. "anota una venta..."), esa parte queda en el historial y
    el asistente la retoma en el turno siguiente, después de guardar el nombre.
    """
    return {
        "messages": [
            AIMessage(
                content=(
                    "¡Hola! Soy Julieta, la asistente de Daniela 👋 "
                    "Antes de partir, ¿cuál es tu nombre?"
                )
            )
        ]
    }


def nodo_asistente(state: State, config: RunnableConfig) -> dict:
    """Entiende el mensaje y registra/consulta/actualiza/elimina con las tools.

    El system prompt es DINÁMICO: consulta el almacén por el nombre asociado
    a este thread_id (el número de teléfono) y le dice al LLM si ya lo sabe
    o si debe pedirlo y guardarlo con la tool `guardar_nombre`.
    """
    telefono = config["configurable"]["thread_id"]
    nombre = almacen.obtener_nombre(telefono)
    if nombre:
        contexto_nombre = f"Estás hablando con {nombre}. Salúdalo por su nombre cuando sea natural."
    else:
        contexto_nombre = (
            "Todavía no sabes el nombre de esta persona. Si te lo dice en su "
            "mensaje, guárdalo con la herramienta guardar_nombre antes de "
            "seguir; si no lo ha dicho, pídeselo."
        )

    system = SystemMessage(
        content=(
            "Eres Julieta, la asistente digital de Daniela, ejecutiva de "
            "ventas de telecomunicaciones en Chile. Tu trabajo es registrar, "
            "consultar, actualizar y eliminar su operación diaria usando las "
            "herramientas disponibles: ventas (mct + rut, conectadas altiro o "
            "agendadas), pendientes (bajas, cambios de domicilio, "
            "devoluciones de equipo), portabilidades en espera (rut, "
            "teléfono, compañía) y solicitudes de homepass. "
            "Reglas: 1) SIEMPRE registra con la herramienta que corresponda, "
            "no digas que guardaste algo sin haberla llamado. 2) Si faltan "
            "datos obligatorios (mct, rut, teléfono, compañía), pídelos antes "
            "de registrar — no inventes valores. 3) Confirma cada registro "
            "repitiendo los datos guardados. 4) Para ACTUALIZAR un registro, "
            "hazlo directo (no necesitas confirmación) pero repite el cambio "
            "en tu respuesta. 5) Para ELIMINAR un registro, primero muéstralo "
            "(usa listar_registros o buscar_por_rut si hace falta) y pregunta "
            "explícitamente si confirma que quiere eliminarlo — SOLO llama a "
            "eliminar_registro después de un 'sí' claro en el mismo hilo. "
            "6) Responde breve, clara y profesional, en español. "
            f"{contexto_nombre}"
        )
    )

    temperatura = state.get("temperatura", TEMPERATURA_DEFECTO)
    modelo = llm_con_tools.bind(temperature=temperatura)
    respuesta = modelo.invoke([system] + recortar_jornada(state["messages"]))
    return {"messages": [respuesta]}

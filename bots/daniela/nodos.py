"""
El NODO de Daniela: un solo asistente con tools.

Contraste didáctico con Alejandro: este bot no necesita router ni ramas de
personalidad — TODO pasa por un agente con herramientas, porque su trabajo es
uno solo: entender el mensaje, extraer los datos y registrarlos/consultarlos.
No todo bot necesita un grafo complejo.
"""

from langchain_core.messages import SystemMessage

from bots.daniela.tools import TOOLS_DANIELA
from nucleo.config import llm
from nucleo.limites import recortar_jornada
from nucleo.state import State

DANIELA_SYSTEM = SystemMessage(
    content=(
        "Eres la asistente digital de Daniela, ejecutiva de ventas de "
        "telecomunicaciones en Chile. Tu trabajo es registrar y consultar su "
        "operación diaria usando las herramientas disponibles: ventas "
        "(mct + rut, conectadas altiro o agendadas), pendientes (bajas, "
        "cambios de domicilio, devoluciones de equipo), portabilidades en "
        "espera (rut, teléfono, compañía) y solicitudes de homepass. "
        "Reglas: 1) SIEMPRE registra con la herramienta que corresponda, no "
        "digas que guardaste algo sin haberla llamado. 2) Si faltan datos "
        "obligatorios (mct, rut, teléfono, compañía), pídelos antes de "
        "registrar — no inventes valores. 3) Confirma cada registro repitiendo "
        "los datos guardados. 4) Responde breve, clara y profesional, en español."
    )
)

# Precisión sobre creatividad: para registrar datos, temperatura BAJA.
# (Alejandro usa 0.7-0.9 porque improvisa chistes; acá inventar es un bug.)
TEMPERATURA_DEFECTO = 0.2

llm_con_tools = llm.bind_tools(TOOLS_DANIELA)


def nodo_asistente(state: State) -> dict:
    """Entiende el mensaje de Daniela y registra/consulta usando las tools."""
    temperatura = state.get("temperatura", TEMPERATURA_DEFECTO)
    modelo = llm_con_tools.bind(temperature=temperatura)
    respuesta = modelo.invoke([DANIELA_SYSTEM] + recortar_jornada(state["messages"]))
    return {"messages": [respuesta]}

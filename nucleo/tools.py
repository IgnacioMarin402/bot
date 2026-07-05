"""
TOOLS: funciones que el LLM puede decidir llamar (ToolNode).

Hasta ahora los nodos hacían UNA sola cosa (llamar al LLM, o devolver texto
fijo). Con tools, el LLM puede pedir "ejecuta esta función con estos
argumentos" en vez de responder directo — y el resultado vuelve a él para
que arme la respuesta final. Es un nuevo tipo de arista: chat -> tools -> chat.

El decorador `@tool` convierte una función normal en algo que el LLM entiende:
lee el nombre, los tipos y el DOCSTRING para saber cuándo y cómo usarla — por
eso el docstring no es opcional, es la instrucción de uso para el modelo.

Elegidas a propósito SIN dependencias externas ni API keys: se prueban en
aislamiento (sin gastar el LLM) y no cuestan nada por llamada.
"""

import random
from datetime import datetime

from langchain_core.tools import tool


@tool
def hora_actual() -> str:
    """Devuelve la fecha y hora actual. Úsala si te preguntan qué hora es o qué día es."""
    return datetime.now().strftime("%A %d de %B, %H:%M")


@tool
def tirar_dado(caras: int = 6) -> str:
    """Tira un dado de N caras (por defecto 6) y devuelve el resultado.

    Úsala cuando te pidan tirar un dado, decidir algo al azar, o "échale
    la suerte".
    """
    resultado = random.randint(1, caras)
    return f"Salió {resultado} (dado de {caras} caras)"


# Registro de tools disponibles. Añadir una tool = escribirla arriba + agregarla aquí.
TOOLS = [hora_actual, tirar_dado]

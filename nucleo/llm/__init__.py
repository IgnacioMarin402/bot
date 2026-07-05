"""
Selector de LLM: la "inyección de dependencia" del proyecto.

`crear_llm()` mira LLM_PROVIDER en el .env y devuelve el adaptador que toca.
Rotar de proveedor = cambiar UNA línea del .env, sin tocar el código.
"""
import os

from langchain_core.language_models import BaseChatModel

from nucleo.llm.proveedores import PROVEEDORES


def crear_llm() -> BaseChatModel:
    nombre = os.getenv("LLM_PROVIDER", "openrouter").lower()
    if nombre not in PROVEEDORES:
        opciones = ", ".join(PROVEEDORES)
        raise SystemExit(
            f"LLM_PROVIDER='{nombre}' no existe. Opciones válidas: {opciones}"
        )
    return PROVEEDORES[nombre]()  # llama al adaptador elegido

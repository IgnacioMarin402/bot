"""
Selector de LLM: la "inyección de dependencia" del proyecto.

`crear_llm()` mira LLM_PROVIDER en el .env y devuelve el adaptador que toca.
Rotar de proveedor = cambiar UNA línea del .env, sin tocar el código.
"""

import os

from langchain_core.language_models import BaseChatModel

from nucleo.llm.proveedores import PROVEEDORES, VISION


def nombre_proveedor() -> str:
    """El proveedor activo según .env (mismo default que crear_llm)."""
    return os.getenv("LLM_PROVIDER", "openrouter").lower()


def crear_llm() -> BaseChatModel:
    nombre = nombre_proveedor()
    if nombre not in PROVEEDORES:
        opciones = ", ".join(PROVEEDORES)
        raise SystemExit(f"LLM_PROVIDER='{nombre}' no existe. Opciones válidas: {opciones}")
    return PROVEEDORES[nombre]()  # llama al adaptador elegido


def tiene_vision() -> bool:
    """True si el proveedor activo puede interpretar imágenes."""
    return nombre_proveedor() in VISION

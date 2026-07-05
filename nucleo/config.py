"""
Configuración central del proyecto.

Carga el .env y crea el modelo (LLM) UNA sola vez, delegando la elección del
proveedor al selector (nucleo/llm). El resto del código solo hace:

    from nucleo.config import llm
"""
from dotenv import load_dotenv

from nucleo.llm import crear_llm

# Carga las variables del .env (LLM_PROVIDER + la key del proveedor elegido).
load_dotenv()

# El modelo ya inyectado. Cambiar de proveedor se hace desde el .env, no aquí.
llm = crear_llm()

"""
Configuración central del proyecto.

Carga el .env y crea el modelo (LLM) UNA sola vez, delegando la elección del
proveedor al selector (nucleo/llm). El resto del código solo hace:

    from nucleo.config import llm

También expone `ruta_datos()`: el ÚNICO lugar que decide dónde viven los
archivos SQLite. Crítico en Fly.io: el disco del contenedor es EFÍMERO
(cada deploy/reinicio lo borra); los datos deben vivir en un volumen
persistente montado en /data, apuntado con la variable DATOS_DIR.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from nucleo.llm import crear_llm

# Carga las variables del .env (LLM_PROVIDER + la key del proveedor elegido).
load_dotenv()

_RAIZ_PROYECTO = Path(__file__).resolve().parents[1]


def ruta_datos(nombre_archivo: str) -> Path:
    """Dónde vive un archivo de datos (SQLite).

    - Local (sin DATOS_DIR): la raíz del proyecto, como siempre.
    - Fly.io: DATOS_DIR=/data -> el volumen persistente. Sin esto, cada
      deploy BORRA la memoria de los bots y los datos de Daniela.
    """
    base = os.getenv("DATOS_DIR")
    return (Path(base) if base else _RAIZ_PROYECTO) / nombre_archivo


# El modelo ya inyectado. Cambiar de proveedor se hace desde el .env, no aquí.
llm = crear_llm()

"""
TOOLS de Julieta: el puente entre la conversación y el almacén.

El LLM lee los docstrings para decidir cuándo llamar cada una y con qué
argumentos (extrae mct/rut/etc. del mensaje natural de Daniela). Cada tool
devuelve un string de confirmación que el LLM usa para redactar su respuesta.

Separación: las tools NO tocan SQL (eso es de almacen.py); solo validan,
delegan y formatean.

`RunnableConfig` en `guardar_nombre`: LangChain inyecta automáticamente el
`config` de la invocación (que trae `thread_id`) en cualquier tool que declare
un parámetro con ese tipo. El LLM NO lo ve ni lo decide — no aparece en el
schema que se le manda (verificado: `tool.args` no incluye "config"). Así la
tool sabe A QUIÉN pertenece el nombre sin que el modelo tenga que inventar
o pedir el número de teléfono (que ya tenemos gratis del thread_id).
"""

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from bots.julieta import almacen


@tool
def registrar_venta(mct: str, rut: str, conectado_altiro: bool, fecha_agendada: str = "") -> str:
    """Registra una venta/contrato conectado.

    Úsala cuando Daniela reporte una venta o contrato nuevo. Necesitas el mct
    y el rut del cliente — si falta alguno, pídeselo antes de registrar.
    `conectado_altiro` es True si quedó conectado de inmediato; si quedó
    agendado para otro día, pásalo False e incluye `fecha_agendada`.
    """
    estado = "conectado" if conectado_altiro else "agendado"
    numero = almacen.guardar_venta(mct, rut, estado, fecha_agendada)
    extra = f" (agendada para {fecha_agendada})" if fecha_agendada else ""
    return f"Venta #{numero} registrada: MCT {mct}, rut {rut}, {estado}{extra}."


@tool
def registrar_pendiente(tipo: str, detalle: str, mct: str = "", rut: str = "") -> str:
    """Registra un pendiente: una baja no completada, un cambio de domicilio,
    una devolución de equipo, u otro trámite inconcluso.

    `tipo` debe ser uno de: 'baja', 'cambio_domicilio', 'devolucion_equipo', 'otro'.
    `detalle` describe el caso con las palabras de Daniela.
    Incluye mct y/o rut si los menciona.
    """
    numero = almacen.guardar_pendiente(tipo, detalle, mct, rut)
    return f"Pendiente #{numero} registrado ({tipo}): {detalle}."


@tool
def registrar_portabilidad(rut: str, telefono: str, compania: str, motivo: str = "") -> str:
    """Registra un cliente que quiere hacer portabilidad pero aún no puede.

    Necesitas rut, teléfono y la compañía actual del cliente — si falta
    alguno, pídeselo antes de registrar. `motivo` es por qué está en espera
    (ej: 'tiene boleta con la otra compañía', 'le faltan días').
    """
    numero = almacen.guardar_portabilidad(rut, telefono, compania, motivo)
    extra = f" — en espera: {motivo}" if motivo else ""
    return f"Portabilidad #{numero} registrada: rut {rut}, tel {telefono}, {compania}{extra}."


@tool
def registrar_homepass(detalle: str) -> str:
    """Registra una solicitud de creación de homepass hecha a soporte.

    `detalle` describe qué se pidió (dirección, cliente, etc.).
    """
    numero = almacen.guardar_homepass(detalle)
    return f"Homepass #{numero} registrado: {detalle}."


@tool
def listar_registros(categoria: str, limite: int = 10) -> str:
    """Muestra los últimos registros de una categoría.

    `categoria` debe ser una de: 'ventas', 'pendientes', 'portabilidades',
    'homepass'. Úsala cuando Daniela pida ver, revisar o repasar lo guardado,
    o cuando necesites el ID de un registro para actualizarlo o eliminarlo.
    """
    try:
        filas = almacen.listar(categoria, limite)
    except ValueError as error:
        return str(error)
    if not filas:
        return f"No hay registros en {categoria} todavía."
    lineas = [f"Últimos {len(filas)} de {categoria}:"]
    for f in filas:
        datos = ", ".join(f"{k}: {v}" for k, v in f.items() if k != "id" and v != "")
        lineas.append(f"  #{f['id']} — {datos}")
    return "\n".join(lineas)


@tool
def buscar_por_rut(rut: str) -> str:
    """Busca TODO lo asociado a un rut (ventas, pendientes y portabilidades).

    Úsala cuando Daniela pregunte por un cliente específico, o para encontrar
    el ID de un registro que quiera actualizar o eliminar.
    """
    resultado = almacen.buscar_por_rut(rut)
    if not resultado:
        return f"No encontré nada para el rut {rut}."
    lineas = [f"Registros del rut {rut}:"]
    for categoria, filas in resultado.items():
        for f in filas:
            datos = ", ".join(
                f"{k}: {v}" for k, v in f.items() if k not in ("id", "rut") and v != ""
            )
            lineas.append(f"  [{categoria}] #{f['id']} — {datos}")
    return "\n".join(lineas)


@tool
def actualizar_registro(categoria: str, numero: int, campo: str, nuevo_valor: str) -> str:
    """Cambia UN campo de UN registro ya guardado.

    `categoria`: 'ventas', 'pendientes', 'portabilidades' u 'homepass'.
    `numero`: el ID del registro (usa listar_registros o buscar_por_rut si
    no lo tienes). `campo` según la categoría:
    - ventas: mct, rut, estado, fecha_agendada
    - pendientes: tipo, detalle, mct, rut
    - portabilidades: rut, telefono, compania, motivo
    - homepass: detalle

    No hace falta pedir confirmación para actualizar — pero repite el
    cambio hecho en tu respuesta para que Daniela lo confirme visualmente.
    """
    try:
        existia = almacen.actualizar(categoria, numero, campo, nuevo_valor)
    except ValueError as error:
        return str(error)
    if not existia:
        return f"No encontré el #{numero} en {categoria}."
    return f"{categoria} #{numero} actualizado: {campo} = {nuevo_valor}."


@tool
def eliminar_registro(categoria: str, numero: int) -> str:
    """Elimina PERMANENTEMENTE un registro.

    `categoria`: 'ventas', 'pendientes', 'portabilidades' u 'homepass'.
    `numero`: el ID del registro.

    IMPORTANTE: solo llama esta herramienta DESPUÉS de que Daniela confirme
    explícitamente que quiere eliminar (ej. responda "sí" a tu pregunta de
    confirmación). Antes de eso, muéstrale el registro (con listar_registros
    o buscar_por_rut si hace falta) y pregunta si está segura. Nunca elimines
    sin haber pedido y recibido esa confirmación en el mismo intercambio.
    """
    try:
        existia = almacen.eliminar(categoria, numero)
    except ValueError as error:
        return str(error)
    if not existia:
        return f"No encontré el #{numero} en {categoria}."
    return f"{categoria} #{numero} eliminado."


@tool
def guardar_nombre(nombre: str, config: RunnableConfig) -> str:
    """Guarda el nombre de la persona con la que estás hablando.

    Úsala apenas el usuario te diga su nombre (por ejemplo, respondiendo a tu
    saludo inicial). No le pidas el número de teléfono: ya lo sabes.
    """
    telefono = config["configurable"]["thread_id"]
    almacen.guardar_nombre(telefono, nombre)
    return f"Nombre guardado: {nombre}."


# Registro de tools del bot. Añadir una tool = escribirla arriba + sumarla aquí.
TOOLS_JULIETA = [
    registrar_venta,
    registrar_pendiente,
    registrar_portabilidad,
    registrar_homepass,
    listar_registros,
    buscar_por_rut,
    actualizar_registro,
    eliminar_registro,
    guardar_nombre,
]

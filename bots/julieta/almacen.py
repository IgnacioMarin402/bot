"""
ALMACÉN de datos de Julieta: los 4 "Excel" de Daniela convertidos en tablas
SQLite, más el registro de usuarios (número -> nombre).

| Tabla          | Reemplaza al Excel de...                                   |
|----------------|------------------------------------------------------------|
| ventas         | contratos conectados (mct, rut, conectado altiro/agendado)  |
| pendientes     | bajas incompletas, cambios de domicilio, devolución equipos |
| portabilidades | clientes esperando portar (boleta con otra cía / faltan días)|
| homepass       | creaciones de homepass solicitadas a soporte                |
| usuarios       | número de teléfono -> nombre (para saludar por su nombre)   |

Diseño: conexión POR OPERACIÓN (abrir → operar → cerrar). Es lo más simple y
seguro con FastAPI atendiendo en varios hilos: cero estado compartido, cero
locks. Para este volumen (una ejecutiva registrando ventas) sobra; un sistema
de alto tráfico usaría un pool de conexiones.

Este módulo NO conoce al LLM ni a las tools: solo sabe guardar y leer datos.
(Las tools lo usan; separar "qué se guarda" de "cómo se conversa" permite
testear el almacén sin gastar API.)
"""

import sqlite3
from datetime import datetime

from nucleo.config import ruta_datos

RUTA_DATOS = ruta_datos("datos_julieta.sqlite")

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS ventas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mct TEXT NOT NULL,
    rut TEXT NOT NULL,
    estado TEXT NOT NULL,          -- 'conectado' o 'agendado'
    fecha_agendada TEXT DEFAULT '',
    creado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pendientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,            -- 'baja', 'cambio_domicilio', 'devolucion_equipo', 'otro'
    detalle TEXT NOT NULL,
    mct TEXT DEFAULT '',
    rut TEXT DEFAULT '',
    creado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS portabilidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rut TEXT NOT NULL,
    telefono TEXT NOT NULL,
    compania TEXT NOT NULL,
    motivo TEXT DEFAULT '',        -- ej: 'boleta con otra compañía', 'faltan días'
    creado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS homepass (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detalle TEXT NOT NULL,
    creado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usuarios (
    telefono TEXT PRIMARY KEY,     -- el thread_id de WhatsApp (ej. "whatsapp:+569...")
    nombre TEXT NOT NULL,
    creado TEXT NOT NULL
);
"""

# Categorías válidas para listar/buscar/actualizar/eliminar. Whitelist: el
# nombre de tabla jamás se interpola desde texto libre (evita inyección SQL
# vía el LLM, que es quien decide los argumentos de estas funciones).
CATEGORIAS = ("ventas", "pendientes", "portabilidades", "homepass")

# Columnas editables por categoría (whitelist igual que CATEGORIAS: ni `id`
# ni `creado` son editables — son identidad/auditoría, no datos de negocio).
CAMPOS_EDITABLES = {
    "ventas": ("mct", "rut", "estado", "fecha_agendada"),
    "pendientes": ("tipo", "detalle", "mct", "rut"),
    "portabilidades": ("rut", "telefono", "compania", "motivo"),
    "homepass": ("detalle",),
}


def _conectar() -> sqlite3.Connection:
    conexion = sqlite3.connect(RUTA_DATOS)
    conexion.executescript(_ESQUEMA)  # idempotente (IF NOT EXISTS)
    return conexion


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def guardar_venta(mct: str, rut: str, estado: str, fecha_agendada: str = "") -> int:
    with _conectar() as c:
        cursor = c.execute(
            "INSERT INTO ventas (mct, rut, estado, fecha_agendada, creado) VALUES (?, ?, ?, ?, ?)",
            (mct, rut, estado, fecha_agendada, _ahora()),
        )
        return cursor.lastrowid


def guardar_pendiente(tipo: str, detalle: str, mct: str = "", rut: str = "") -> int:
    with _conectar() as c:
        cursor = c.execute(
            "INSERT INTO pendientes (tipo, detalle, mct, rut, creado) VALUES (?, ?, ?, ?, ?)",
            (tipo, detalle, mct, rut, _ahora()),
        )
        return cursor.lastrowid


def guardar_portabilidad(rut: str, telefono: str, compania: str, motivo: str = "") -> int:
    with _conectar() as c:
        cursor = c.execute(
            "INSERT INTO portabilidades (rut, telefono, compania, motivo, creado) VALUES (?, ?, ?, ?, ?)",
            (rut, telefono, compania, motivo, _ahora()),
        )
        return cursor.lastrowid


def guardar_homepass(detalle: str) -> int:
    with _conectar() as c:
        cursor = c.execute(
            "INSERT INTO homepass (detalle, creado) VALUES (?, ?)",
            (detalle, _ahora()),
        )
        return cursor.lastrowid


def listar(categoria: str, limite: int = 10) -> list[dict]:
    """Últimos registros de una categoría, el más reciente primero."""
    if categoria not in CATEGORIAS:
        raise ValueError(f"Categoría '{categoria}' no existe. Opciones: {CATEGORIAS}")
    with _conectar() as c:
        c.row_factory = sqlite3.Row
        filas = c.execute(
            f"SELECT * FROM {categoria} ORDER BY id DESC LIMIT ?",  # noqa: S608 (whitelist)
            (limite,),
        ).fetchall()
        return [dict(f) for f in filas]


def buscar_por_rut(rut: str) -> dict[str, list[dict]]:
    """Busca el rut en todas las tablas que lo tienen. Devuelve {categoria: filas}."""
    resultado = {}
    with _conectar() as c:
        c.row_factory = sqlite3.Row
        for tabla in ("ventas", "pendientes", "portabilidades"):
            filas = c.execute(
                f"SELECT * FROM {tabla} WHERE rut = ? ORDER BY id DESC",  # noqa: S608
                (rut,),
            ).fetchall()
            if filas:
                resultado[tabla] = [dict(f) for f in filas]
    return resultado


def actualizar(categoria: str, id_registro: int, campo: str, valor: str) -> bool:
    """Cambia UN campo de UN registro. True si el registro existía.

    `categoria` y `campo` se validan contra whitelists (CATEGORIAS,
    CAMPOS_EDITABLES) — nunca se interpolan directo desde lo que decide el LLM.
    """
    if categoria not in CATEGORIAS:
        raise ValueError(f"Categoría '{categoria}' no existe. Opciones: {CATEGORIAS}")
    if campo not in CAMPOS_EDITABLES[categoria]:
        raise ValueError(
            f"Campo '{campo}' no es editable en {categoria}. Opciones: {CAMPOS_EDITABLES[categoria]}"
        )
    with _conectar() as c:
        cursor = c.execute(
            f"UPDATE {categoria} SET {campo} = ? WHERE id = ?",  # noqa: S608 (whitelist)
            (valor, id_registro),
        )
        return cursor.rowcount > 0


def eliminar(categoria: str, id_registro: int) -> bool:
    """Borra UN registro por id. True si existía (y se borró)."""
    if categoria not in CATEGORIAS:
        raise ValueError(f"Categoría '{categoria}' no existe. Opciones: {CATEGORIAS}")
    with _conectar() as c:
        cursor = c.execute(
            f"DELETE FROM {categoria} WHERE id = ?",  # noqa: S608 (whitelist)
            (id_registro,),
        )
        return cursor.rowcount > 0


def obtener_nombre(telefono: str) -> str | None:
    """El nombre guardado para este número, o None si nunca lo dio."""
    with _conectar() as c:
        fila = c.execute("SELECT nombre FROM usuarios WHERE telefono = ?", (telefono,)).fetchone()
        return fila[0] if fila else None


def guardar_nombre(telefono: str, nombre: str) -> None:
    """Guarda (o reemplaza) el nombre asociado a un número de teléfono."""
    with _conectar() as c:
        c.execute(
            "INSERT INTO usuarios (telefono, nombre, creado) VALUES (?, ?, ?) "
            "ON CONFLICT(telefono) DO UPDATE SET nombre = excluded.nombre",
            (telefono, nombre, _ahora()),
        )

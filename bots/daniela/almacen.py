"""
ALMACÉN de datos de Daniela: los 4 "Excel" convertidos en tablas SQLite.

| Tabla          | Reemplaza al Excel de...                                   |
|----------------|------------------------------------------------------------|
| ventas         | contratos conectados (mct, rut, conectado altiro/agendado)  |
| pendientes     | bajas incompletas, cambios de domicilio, devolución equipos |
| portabilidades | clientes esperando portar (boleta con otra cía / faltan días)|
| homepass       | creaciones de homepass solicitadas a soporte                |

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
from pathlib import Path

RUTA_DATOS = Path(__file__).resolve().parents[2] / "datos_daniela.sqlite"

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
"""

# Categorías válidas para listar/buscar. Whitelist: el nombre de tabla jamás
# se interpola desde texto libre (evita inyección SQL vía el LLM).
CATEGORIAS = ("ventas", "pendientes", "portabilidades", "homepass")


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

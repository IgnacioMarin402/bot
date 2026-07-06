"""
bots/: los bots del proyecto (hoy son dos: Alejandro y Daniela).

`obtener_bot(nombre)` devuelve el grafo compilado del bot pedido. Los imports
son perezosos para que pedir un bot NO construya el otro (cada grafo abre su
propia base SQLite de memoria).

Cada bot vive en su carpeta (bots/alejandro/, bots/daniela/) y ambos
comparten la plataforma de nucleo/: LLM multi-proveedor, State, protecciones
y responder().
"""


def obtener_bot(nombre: str):
    """Devuelve el grafo compilado del bot pedido (import perezoso)."""
    if nombre == "alejandro":
        from bots.alejandro.grafo import obtener_grafo
    elif nombre == "daniela":
        from bots.daniela.grafo import obtener_grafo
    else:
        raise SystemExit(f"Bot '{nombre}' no existe. Opciones: alejandro, daniela")
    return obtener_grafo()

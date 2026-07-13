"""Dibuja el grafo de un bot — en texto (Mermaid) y como PNG.

Uso:  python ver_grafo.py [alejandro|julieta]   (default: alejandro)
"""

import sys

from bots import obtener_bot

nombre = sys.argv[1] if len(sys.argv) > 1 else "alejandro"
grafo = obtener_bot(nombre)

# 1) Versión texto (Mermaid): siempre funciona, sin internet.
print(f"=== Grafo de {nombre} (pega este texto en https://mermaid.live) ===")
print(grafo.get_graph().draw_mermaid())

# 2) Versión PNG: usa el servicio mermaid.ink (requiere internet).
try:
    png = grafo.get_graph().draw_mermaid_png()
    ruta = rf"C:\Users\doomb\OneDrive\Escritorio\proyectos\graph\grafo_{nombre}.png"
    with open(ruta, "wb") as f:
        f.write(png)
    print("\nPNG guardado en:", ruta)
except Exception as e:
    print("\nNo se pudo generar PNG (¿sin internet?):", e)

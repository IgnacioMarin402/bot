"""Dibuja el grafo — en texto (Mermaid) y como PNG."""

from nucleo.grafo import obtener_grafo

grafo = obtener_grafo()

# 1) Versión texto (Mermaid): siempre funciona, sin internet.
print("=== Diagrama Mermaid (pega este texto en https://mermaid.live) ===")
print(grafo.get_graph().draw_mermaid())

# 2) Versión PNG: usa el servicio mermaid.ink (requiere internet).
try:
    png = grafo.get_graph().draw_mermaid_png()
    ruta = r"C:\Users\doomb\OneDrive\Escritorio\proyectos\graph\grafo.png"
    with open(ruta, "wb") as f:
        f.write(png)
    print("\nPNG guardado en:", ruta)
except Exception as e:
    print("\nNo se pudo generar PNG (¿sin internet?):", e)

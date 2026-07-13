"""
Punto de entrada del proyecto.

Uso:
    python main.py             -> chatea con Alejandro (default)
    python main.py julieta     -> chatea con Julieta, la asistente de Daniela

Estructura (arquitectura Ports & Adapters):

    nucleo/        <- plataforma compartida (LLM, State, protecciones)
    bots/alejandro/<- el bot Alejandro (nodos, router, tools, grafo)
    bots/julieta/  <- el bot Julieta (almacén, tools, nodo, grafo)
    interfaces/    <- adaptadores: cli.py (terminal) y whatsapp.py (webhook)

Regla de oro: nucleo/ NUNCA importa de interfaces/. Solo al revés.
"""

import sys

from interfaces.cli import iniciar_cli

if __name__ == "__main__":
    bot = sys.argv[1] if len(sys.argv) > 1 else "alejandro"
    iniciar_cli(bot)

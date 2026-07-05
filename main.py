"""
Punto de entrada del proyecto.

Estructura (arquitectura Ports & Adapters):

    nucleo/        <- la lógica del bot (no sabe si es CLI o WhatsApp)
      config.py    <- crea el LLM (lee .env)
      state.py     <- el State
      nodos.py     <- nodo_chat, nodo_broma, nodo_once, nodo_flojera
      router.py    <- la lógica de decisión (arista condicional)
      grafo.py     <- arma y compila el grafo
    interfaces/    <- adaptadores que hablan con el nucleo
      cli.py       <- bucle de terminal
      whatsapp.py  <- (futuro) webhook

Regla de oro: nucleo/ NUNCA importa de interfaces/. Solo al revés.
"""

from interfaces.cli import iniciar_cli

if __name__ == "__main__":
    iniciar_cli()

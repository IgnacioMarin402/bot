"""
Interfaz de TERMINAL (adaptador).

Traduce entre el usuario en la consola y el grafo. Fíjate que este archivo
NO sabe nada de nodos, routing ni tools: solo llama a `responder()`. Ese es
el punto de la arquitectura — whatsapp.py hace lo mismo sin tocar el nucleo/.
"""

from langchain_core.messages import HumanMessage

from bots import obtener_bot
from nucleo.ejecucion import responder


def iniciar_cli(nombre_bot: str = "alejandro"):
    grafo = obtener_bot(nombre_bot)
    etiqueta = nombre_bot.capitalize()
    print(f"Hablando con {etiqueta}:")
    print("(Escribe 'salir' para terminar)\n")

    # El thread_id identifica ESTA conversación. Cámbialo y empiezas de cero.
    # Cada bot tiene su propia memoria SQLite, así que no se mezclan.
    thread_id = f"cli-{nombre_bot}"

    while True:
        entrada = input("Tú: ").strip()
        if entrada.lower() in ("salir", "exit", "quit"):
            print("¡Hasta luego! 👋")
            break
        if not entrada:
            continue

        # responder() puede devolver más de un mensaje (ej. saludo + respuesta
        # la primera vez que este thread_id escribe).
        for texto in responder(HumanMessage(content=entrada), thread_id, grafo=grafo):
            print(f"{etiqueta}:", texto)
        print()

"""
Interfaz de TERMINAL (adaptador).

Traduce entre el usuario en la consola y el grafo. Fíjate que este archivo
NO sabe nada de nodos, routing ni tools: solo llama a `responder()`. Ese es
el punto de la arquitectura — whatsapp.py hace lo mismo sin tocar el nucleo/.
"""

from langchain_core.messages import HumanMessage

from nucleo.grafo import responder


def iniciar_cli():
    print("Pídele algo a Alejandro:")
    print("(Escribe 'salir' para terminar)\n")

    # El thread_id identifica ESTA conversación. Cámbialo y empiezas de cero.
    thread_id = "yo-soy-el-jefe-malo"

    while True:
        entrada = input("Tú: ").strip()
        if entrada.lower() in ("salir", "exit", "quit"):
            print("¡Buen fin de semana! 👋")
            break
        if not entrada:
            continue

        # responder() puede devolver más de un mensaje (ej. saludo + respuesta
        # la primera vez que este thread_id escribe).
        for texto in responder(HumanMessage(content=entrada), thread_id):
            print("Alejandro:", texto)
        print()

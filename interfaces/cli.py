"""
Interfaz de TERMINAL (adaptador).

Traduce entre el usuario en la consola y el grafo. Fíjate que este archivo
NO sabe nada de nodos ni de routing: solo habla con `grafo`. Ese es el punto
de la arquitectura — mañana whatsapp.py hará lo mismo sin tocar el nucleo/.
"""
from langchain_core.messages import HumanMessage

from nucleo.grafo import grafo


def iniciar_cli():
    print("Pídele algo a Alejandro:")
    print("(Escribe 'salir' para terminar)\n")

    # El thread_id identifica ESTA conversación. Cámbialo y empiezas de cero.
    config = {"configurable": {"thread_id": "yo-soy-el-jefe-malo"}}

    while True:
        entrada = input("Tú: ").strip()
        if entrada.lower() in ("salir", "exit", "quit"):
            print("¡Buen fin de semana! 👋")
            break
        if not entrada:
            continue

        # Solo pasamos el mensaje NUEVO; la memoria (checkpointer) recuerda el resto.
        resultado = grafo.invoke(
            {"messages": [HumanMessage(content=entrada)]},
            config=config,
        )
        # .text extrae el texto plano (algunos modelos devuelven bloques).
        print("Alejandro:", resultado["messages"][-1].text, "\n")

"""
EJECUCIÓN: la función `responder()` que usan todas las interfaces, con
cualquier bot.

    from bots import obtener_bot
    from nucleo.ejecucion import responder

    textos = responder(HumanMessage(content="hola"), thread_id="...",
                       grafo=obtener_bot("alejandro"))

Esto es plataforma pura: protecciones, marca de tiempo y cálculo del delta
de mensajes son iguales para todos los bots. Por eso vive en nucleo/ y NO
conoce a ningún bot en particular (la regla de dependencias: nucleo no
importa de bots/ ni de interfaces/ — solo al revés).
"""

from langchain_core.messages import AIMessage, BaseMessage

from nucleo.limites import marcar_tiempo, mensaje_demasiado_largo, permitir_mensaje


def responder(mensaje: BaseMessage, thread_id: str, grafo) -> list[str]:
    """Invoca un grafo y devuelve los TEXTOS nuevos para mostrarle al usuario.

    Por qué puede ser más de uno: un turno puede agregar varios mensajes al
    historial (ej. saludo + respuesta la primera vez). Por qué hay que
    filtrar: durante el loop de tools también se agregan un AIMessage sin
    texto (solo con tool_calls) y un ToolMessage con el resultado crudo —
    ninguno de los dos es para mostrar, son pasos internos del LLM.

    Protecciones (ver nucleo/limites.py): se aplican ANTES de invocar el
    grafo — rechazar barato y temprano. Los rechazos responden texto fijo,
    sin LLM y SIN guardar nada en el historial (evita costo y contaminación).
    El orden importa: primero el largo (gratis, no consume cupo del rate
    limit) y después el rate limit (que sí registra la llamada aceptada).
    """
    if mensaje_demasiado_largo(mensaje):
        return ["¿Me mandaste la biblia? Resume po, que no pago por leer novelas 😵"]
    if not permitir_mensaje(thread_id):
        return ["Calma po, una consulta a la vez. No soy call center 😤"]

    # Estampa la hora de llegada: la usa el recorte de jornada (limites.py)
    # para decidir qué parte del historial se le envía al LLM.
    marcar_tiempo(mensaje)

    config = {"configurable": {"thread_id": thread_id}}
    previos = grafo.get_state(config).values.get("messages", [])
    resultado = grafo.invoke({"messages": [mensaje]}, config=config)
    nuevos = resultado["messages"][len(previos) :]

    return [m.text for m in nuevos if isinstance(m, AIMessage) and m.text]

"""
La ARISTA CONDICIONAL (el "if" del grafo).

`router` mira el último mensaje del usuario y devuelve el NOMBRE del nodo
al que hay que ir. LangGraph usa ese nombre para elegir la rama.

Lección aprendida (bug real, 2026-07-05): buscar subcadenas con `in` hace
que "once" matchee dentro de "entONCEs". Hay que comparar PALABRAS completas:
`\b` en regex significa "frontera de palabra" (inicio/fin de una palabra).

Nota sobre `flojera` (2026-07-06): antes se activaba por LARGO del mensaje
(>30 caracteres). Se cambió a detectar IMPEDIMENTOS (problemas, bugs, cosas
que no funcionan) porque es lo que de verdad hace que un jefe evada ayudar.
Es una heurística por patrones (no un clasificador con LLM): gratis, instantánea
y testeable sin gastar API, pero no es perfecta — frases de impedimento muy
distintas a las listadas no van a matchear. Si esto se vuelve limitante, la
evolución natural es un nodo clasificador con LLM (ver memory/roadmap.md).

Se usa `.text` y no `.content` (2026-07-06): con mensajes multimodales (foto
+ texto) `.content` es una LISTA de bloques, no un string — `.lower()` sobre
eso revienta con AttributeError. `.text` normaliza y devuelve solo el texto
en ambos casos (bug real, cazado antes de llegar a producción).

Se busca el último HumanMessage, no `state["messages"][-1]` a secas
(2026-07-06, otro bug real): desde que existe el nodo "saludo", el router se
vuelve a evaluar DESPUÉS de que saludo agregó su propia respuesta al
historial — en ese momento el último mensaje es el DEL BOT, no el del
usuario. Mirar ciegamente `[-1]` hacía que el saludo de Alejandro se
clasificara como si fuera la pregunta del usuario. El router siempre debe
decidir según lo que el USUARIO escribió, sin importar qué nodos corrieron
antes en el mismo turno.
"""

import re

from langchain_core.messages import HumanMessage

from nucleo.state import State

palabras_once = ("11", "once")
palabras_broma = ("urgente", "por favor", "necesito")

# Frases/raíces típicas de "tengo un impedimento" — español neutro + jerga chilena.
# Son sub-strings deliberadamente (no palabras sueltas), así que no hace falta \b:
# "me eché x programa" no se confunde con nada más corto.
patrones_impedimento = (
    "tengo un problema",
    "tengo un bug",
    "hay un bug",
    "no funciona",
    "no me funciona",
    "no anda",
    "no puedo avanzar",
    "no sé cómo",
    "no se como",
    "se cayó",
    "se cayo",
    "se rompió",
    "se rompio",
    "me pidieron más",
    "me pidieron mas",
    "me agregaron más",
    "me agregaron mas",
    "quedé atascado",
    "quede atascado",
    "quedé pegado",
    "quede pegado",
    "estoy atascado",
    "estoy atascada",
    "estoy trabado",
    "estoy trabada",
    "se echó a perder",
    "se echo a perder",
    "me eché",  # "me eché [el programa/proyecto/build]"
    "me eche",
    "cagué",  # jerga chilena: "cagué la cobertura", "cagué el deploy"
    "cague",
    "me pifié",  # "me pifié" / "me pifio"
    "me pifie",
    "me equivoqué",
    "me equivoque",
    "me confundí",
    "me confundi",
    "me trabé",
    "me trabe",
    "me colgué",
    "me colgue",
    "me quedé pegado",
    "me quede pegado",
    "me quedé atascado",
    "me quede atascado",
    "me quedé trabado",
    "me quede trabado",
    "me pitié",
    "me pitie",
    "me falló",
    "me fallo",
)


def _contiene_palabra(texto: str, palabra: str) -> bool:
    """True si `palabra` aparece COMPLETA en el texto (no como pedazo de otra).
    Sólo validar último mensaje.
    "once" -> matchea en todo lo que termine en once".
    Funciona también con todo tipo de frases y números que 11 o que finalicen en 11.
    """
    return re.search(rf"\b{re.escape(palabra)}\b", texto) is not None


def _tiene_impedimento(texto: str) -> bool:
    """True si el texto contiene alguna frase típica de "tengo un problema"."""
    return any(patron in texto for patron in patrones_impedimento)


def _ultimo_mensaje_usuario(state: State) -> str:
    """Texto del último mensaje escrito por el USUARIO (no por el bot).

    Recorre desde el final buscando el HumanMessage más reciente. Necesario
    porque un turno puede tener nodos intermedios (ej. "saludo") que agregan
    SU PROPIA respuesta antes de que el router se vuelva a evaluar.
    """
    for mensaje in reversed(state["messages"]):
        if isinstance(mensaje, HumanMessage):
            return mensaje.text.lower()
    return state["messages"][-1].text.lower()  # defensivo: no debería pasar


def router(state: State) -> str:
    ultimo = _ultimo_mensaje_usuario(state)
    if any(_contiene_palabra(ultimo, p) for p in palabras_broma):
        return "broma"
    elif any(_contiene_palabra(ultimo, p) for p in palabras_once):
        return "once"
    elif _tiene_impedimento(ultimo):
        return "flojera"
    return "chat"


def es_primera_vez(state: State) -> bool:
    """True si nadie le ha escrito antes a este thread_id.

    Por qué funciona: cuando LangGraph ejecuta el grafo, `state["messages"]`
    YA incluye el historial cargado del checkpointer + el mensaje nuevo que
    se acaba de mandar (el merge del reducer pasa ANTES de correr los nodos).
    Entonces, si la lista tiene un solo elemento, es porque no había historial
    previo: este thread_id le está escribiendo al bot por primera vez.
    """
    return len(state["messages"]) <= 1


def router_entrada(state: State) -> str:
    """Arista desde START (2026-07-06): intercepta el PRIMER mensaje de cada
    conversación para mandarlo al nodo "saludo" antes que a cualquier otro.
    El resto de las veces, delega en `router` (la lógica de siempre).
    """
    if es_primera_vez(state):
        return "saludo"
    return router(state)

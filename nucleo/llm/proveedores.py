"""
ADAPTADORES de LLM (Ports & Adapters aplicado al modelo).

El "puerto" (interfaz común) NO lo inventamos nosotros: es `BaseChatModel`
de LangChain. Todos los ChatXxx lo implementan, así que exponen el mismo
.invoke()/.stream(). Por eso el grafo funciona igual con cualquiera.

Cada función de aquí es un ADAPTADOR: construye un modelo concreto y devuelve
algo que cumple el puerto (BaseChatModel). Se registran en PROVEEDORES para
poder ROTAR por nombre desde el .env (LLM_PROVIDER=gemini, claude, ...).

Los imports son perezosos (dentro de cada función) para que, si no tienes
instalada una librería, solo falle ESE proveedor y no todo el programa.
"""

import os

from langchain_core.language_models import BaseChatModel


def _exigir(clave: str) -> str:
    """Devuelve la key del entorno o corta con un mensaje claro."""
    valor = os.getenv(clave)
    if not valor:
        raise SystemExit(f"Falta {clave} en tu .env para usar este proveedor.")
    return valor


def openrouter() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model="deepseek/deepseek-chat",
        base_url="https://openrouter.ai/api/v1",
        api_key=_exigir("OPENROUTER_API_KEY"),
        temperature=0.7,
    )


def gemini() -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    _exigir("GOOGLE_API_KEY")  # la librería la lee sola del entorno
    return ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)


def claude() -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    _exigir("ANTHROPIC_API_KEY")
    return ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0.7)


def groq() -> BaseChatModel:
    from langchain_groq import ChatGroq

    _exigir("GROQ_API_KEY")
    return ChatGroq(model="llama-3.3-70b-versatile", temperature=0.7)


def xai() -> BaseChatModel:
    from langchain_xai import ChatXAI

    _exigir("XAI_API_KEY")
    return ChatXAI(model="grok-3", temperature=0.7)


# Registro: nombre -> adaptador. Añadir un proveedor = añadir una línea aquí.
PROVEEDORES = {
    "openrouter": openrouter,
    "gemini": gemini,
    "claude": claude,
    "groq": groq,
    "xai": xai,
}

# Proveedores cuyo modelo configurado arriba SABE interpretar imágenes.
# Verificado: gemini-2.0-flash y claude-haiku-4-5 son multimodales.
# deepseek-chat (openrouter), llama-3.3-70b (groq) y grok-3 (xai) aquí NO
# están confirmados con visión — si cambias esos modelos por versiones que sí
# la tengan, agrega el nombre del proveedor a este set.
VISION = {"gemini", "claude"}

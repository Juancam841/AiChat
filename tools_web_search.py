import logging

from tavily import TavilyClient

from config import TAVILY_API_KEY
from tool_manager import register_tool


logger = logging.getLogger(__name__)



def web_search(
    query,
    max_results=5,
    topic="general",
    time_range=None
):
    """
    Busca información en Internet mediante Tavily.
    Permite búsquedas generales o de noticias con filtro temporal.
    """

    if not TAVILY_API_KEY:
        raise ValueError(
            "No hay una API Key de Tavily configurada."
        )

    if not isinstance(query, str) or not query.strip():
        raise ValueError("La consulta de búsqueda está vacía.")

    if not isinstance(max_results, int) or not 1 <= max_results <= 10:
        raise ValueError(
            "La cantidad de resultados debe estar entre 1 y 10."
        )

    if topic not in ("general", "news"):
        raise ValueError("El tema debe ser general o news.")

    if time_range not in (None, "day", "week", "month", "year"):
        raise ValueError("El rango temporal no es válido.")

    client = TavilyClient(api_key=TAVILY_API_KEY)

    search_options = {
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
        "topic": topic,
        "include_answer": True
    }

    if time_range:
        search_options["time_range"] = time_range

    response = client.search(**search_options)

    return {
        "answer": response.get("answer"),
        "results": [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content"),
                "score": item.get("score"),
                "published_date": item.get("published_date")
            }
            for item in response.get("results", [])
        ]
    }



register_tool(
    name="web_search",
    description="Busca información en Internet. Permite búsquedas generales o noticias con filtros temporales.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Tema o pregunta que se desea investigar."
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "default": 5
            },
            "topic": {
                "type": "string",
                "enum": ["general", "news"],
                "default": "general"
            },
            "time_range": {
                "type": ["string", "null"],
                "enum": ["day", "week", "month", "year", None],
                "default": None
            }
        },
        "required": ["query"],
        "additionalProperties": False
    },
    function=web_search
)

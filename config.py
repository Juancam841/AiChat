import os
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv()

# API Keys de los proveedores de IA
PROVIDERS = {
    "groq": os.getenv("GROQ_API_KEY"),
    "gemini": os.getenv("GEMINI_API_KEY"),
    "openrouter": os.getenv("OPENROUTER_API_KEY"),
    "mistral": os.getenv("MISTRAL_API_KEY"),
}

# API Keys de herramientas externas
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Orígenes del frontend permitidos por CORS; separados por comas.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "AI_CHAT_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]


def get_configured_providers():
    return [
        provider
        for provider, api_key in PROVIDERS.items()
        if api_key
    ]

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


def get_configured_providers():
    return [
        provider
        for provider, api_key in PROVIDERS.items()
        if api_key
    ]
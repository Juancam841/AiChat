import logging
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from usage_manager import get_usage_summary
from config import get_configured_providers

from providers import (
    ask_model,
    ask_model_with_tools,
    ask_model_with_fallback,
    ask_model_with_search_fallback,
    ask_model_with_manual_search
)

from models import get_available_models, supports_tools
from model_router import select_model
from quota_manager import get_model_quotas, is_quota_available

import tools_calculator
import tools_web_search

from tool_manager import get_available_tools

from database import (
    initialize_database,
    create_conversation,
    save_message,
    get_conversation_messages,
    get_conversation,
    get_all_conversations,
    delete_conversation,
    update_conversation_title,
    update_conversation_model
)


logger = logging.getLogger(__name__)


app = FastAPI(
    title="AI Chat",
    description="Mi plataforma personal de inteligencia artificial",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():

    initialize_database()

    logger.info(
        "Herramientas disponibles: %s",
        [
            tool["name"]
            for tool in get_available_tools()
        ]
    )


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1)
    strategy: Literal[
        "free_first",
        "best_available",
        "manual"
    ] = "free_first"
    provider: str | None = None
    model: str | None = None
    web_search: bool = False


@app.get("/")
def home():
    return {
        "message": "AI Chat está funcionando",
        "status": "online"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/providers")
def providers():
    return {
        "configured": get_configured_providers(),
        "supported": [
            provider
            for provider, models in get_available_models().items()
            if models
        ]
    }


@app.get("/models")
def models(provider: str = None):
    return {
        "models": get_available_models(provider)
    }


@app.get("/usage")
def usage():
    try:
        summary = get_usage_summary()

        return {
            "usage": summary
        }

    except Exception:
        logger.exception(
            "Error al consultar el consumo"
        )

        raise HTTPException(
            status_code=500,
            detail="Error al consultar las estadísticas de consumo."
        )


@app.get("/quotas")
def quotas():
    try:
        return {
            "quotas": get_model_quotas()
        }

    except Exception:
        logger.exception(
            "Error al consultar las cuotas"
        )

        raise HTTPException(
            status_code=500,
            detail="Error al consultar las cuotas de los modelos."
        )


@app.get("/conversations")
def list_conversations():
    try:
        conversations = get_all_conversations()

        return {
            "total": len(conversations),
            "conversations": conversations
        }

    except Exception:
        logger.exception(
            "Error al consultar las conversaciones"
        )

        raise HTTPException(
            status_code=500,
            detail="Error al consultar las conversaciones."
        )


@app.get("/conversations/{conversation_id}")
def get_conversation_detail(conversation_id: str):
    try:
        conversation = get_conversation(conversation_id)

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="La conversación no existe."
            )

        messages = get_conversation_messages(conversation_id)

        return {
            "conversation": conversation,
            "messages": messages
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Error al consultar el detalle de la conversación"
        )

        raise HTTPException(
            status_code=500,
            detail="Error al consultar la conversación."
        )


@app.delete("/conversations/{conversation_id}")
def remove_conversation(conversation_id: str):
    try:
        deleted = delete_conversation(conversation_id)

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="La conversación no existe."
            )

        return {
            "message": "Conversación eliminada correctamente.",
            "conversation_id": conversation_id
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Error al eliminar la conversación"
        )

        raise HTTPException(
            status_code=500,
            detail="Error al eliminar la conversación."
        )


@app.post("/chat")
def chat(request: ChatRequest):
    try:

        # 1. Seleccionar proveedor y modelo

        if request.strategy == "manual":

            if not request.provider or not request.model:
                raise ValueError(
                    "La estrategia manual requiere proveedor y modelo."
                )

            provider = request.provider
            model = request.model

            # Validar cuota local del modelo manual

            quotas = get_model_quotas()
            quota = quotas.get(
                f"{provider}/{model}"
            )

            if not is_quota_available(quota):
                raise ValueError(
                    f"El modelo {provider}/{model} alcanzó "
                    "su límite local configurado."
                )

        else:

            selected = select_model(
                capability="general",
                strategy=request.strategy
            )

            provider = selected["provider"]
            model = selected["model"]

        # 2. Recuperar conversación existente o preparar una nueva

        if request.conversation_id is None:
            conversation_id = None
            messages = []

        else:

            conversation_id = request.conversation_id

            conversation = get_conversation(
                conversation_id
            )

            if conversation is None:
                raise HTTPException(
                    status_code=404,
                    detail="La conversación no existe."
                )

            messages = get_conversation_messages(conversation_id)

        # 4. Agregar mensaje del usuario

        messages.append({
            "role": "user",
            "content": request.message
        })

        # 5. Consultar modelo

        search_results = []

        if request.strategy == "manual":

            if request.web_search:

                result = ask_model_with_manual_search(
                    provider=provider,
                    model=model,
                    messages=messages
                )

                response = result["response"]["answer"]

                search_results = result["response"]["results"]

            else:
                if supports_tools(provider, model):
                    response = ask_model_with_tools(
                        provider=provider,
                        model=model,
                        messages=messages,
                        tool_names=["calculator"]
                    )
                else:
                    response = ask_model(
                        provider=provider,
                        model=model,
                        messages=messages
                    )

        else:

            if request.web_search:

                result = ask_model_with_search_fallback(
                    messages=messages,
                    strategy=request.strategy
                )

                response = result["response"]["answer"]

                search_results = result["response"]["results"]

                provider = result["provider"]
                model = result["model"]

            else:

                result = ask_model_with_fallback(
                    messages=messages,
                    strategy=request.strategy
                )

                response = result["response"]
                provider = result["provider"]
                model = result["model"]

        # Crear conversaciones nuevas solo después de una respuesta correcta.
        if conversation_id is None:
            conversation_id = create_conversation(
                provider=provider,
                model=model
            )

        # 6. Guardar mensaje del usuario

        save_message(
            conversation_id,
            "user",
            request.message
        )

        # 7. Asignar título automático

        if request.conversation_id is None:

            title = " ".join(
                request.message.strip().split()
            )

            if len(title) > 50:
                title = title[:47].rstrip() + "..."

            update_conversation_title(
                conversation_id,
                title
            )

        # 8. Guardar respuesta del asistente

        save_message(
            conversation_id,
            "assistant",
            response
        )

        # 9. Actualizar proveedor y modelo utilizados

        update_conversation_model(
            conversation_id,
            provider,
            model
        )

        # 10. Devolver respuesta y fuentes

        return {
            "conversation_id": conversation_id,
            "response": response,
            "results": search_results,
            "model": model,
            "provider": provider
        }

    except HTTPException:
        raise

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception:

        logger.exception(
            "Error al comunicarse con el proveedor de IA"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Error al comunicarse con el proveedor "
                "de inteligencia artificial."
            )
        )

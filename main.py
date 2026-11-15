import logging
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from conversation_context import MAX_CONTEXT_CHARACTERS
from chat_service import ConversationNotFoundError, process_chat

from usage_manager import get_usage_summary, get_usage_summary_page
from config import CORS_ORIGINS, get_configured_providers

from models import get_available_models
from quota_manager import get_model_quotas

from tool_manager import get_available_tools

from database import (
    initialize_database,
    get_conversation_message_page,
    get_conversation,
    get_all_conversations,
    delete_conversation
)


logger = logging.getLogger(__name__)


app = FastAPI(
    title="AI Chat",
    description="Mi plataforma personal de inteligencia artificial",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
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
    message: str = Field(
        min_length=1,
        max_length=MAX_CONTEXT_CHARACTERS
    )
    strategy: Literal[
        "free_first",
        "best_available",
        "manual"
    ] = "free_first"
    provider: str | None = None
    model: str | None = None
    web_search: bool = False
    agent_mode: bool = False


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
    configured = get_configured_providers()
    models_by_provider = get_available_models()
    supported = [
        provider
        for provider, models in models_by_provider.items()
        if models
    ]

    return {
        "configured": configured,
        "supported": supported,
        "available": [
            provider
            for provider in configured
            if models_by_provider.get(provider)
        ]
    }


@app.get("/models")
def models(provider: str = None):
    return {
        "models": get_available_models(provider)
    }


@app.get("/usage")
def usage(
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int | None = Query(default=None, ge=0)
):
    try:
        if limit is None and offset is None:
            return {
                "usage": get_usage_summary()
            }

        page_limit = limit if limit is not None else 25
        page_offset = offset if offset is not None else 0
        return get_usage_summary_page(
            limit=page_limit,
            offset=page_offset
        )

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
def list_conversations(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    try:
        total, conversations = get_all_conversations(limit, offset)

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
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
def get_conversation_detail(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    before_id: int | None = Query(default=None, gt=0)
):
    try:
        conversation = get_conversation(conversation_id)

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="La conversación no existe."
            )

        messages, has_more = get_conversation_message_page(
            conversation_id,
            limit=limit,
            before_id=before_id
        )

        return {
            "conversation": conversation,
            "messages": messages,
            "has_more": has_more
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
        return process_chat(
            conversation_id=request.conversation_id,
            message=request.message,
            strategy=request.strategy,
            provider=request.provider,
            model=request.model,
            web_search=request.web_search,
            agent_mode=request.agent_mode,
        )

    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="La conversación no existe."
        ) from error

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

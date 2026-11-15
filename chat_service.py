import json
import logging

from conversation_context import (
    MAX_CONTEXT_CHARACTERS,
    get_input_token_budget,
    trim_conversation_history,
)
from database import (
    get_conversation,
    get_conversation_messages,
    save_turn,
)
from models import get_context_window, supports_tools
from model_router import get_model_candidates, select_model
from config import TAVILY_API_KEY
from providers import (
    SYSTEM_PROMPT,
    ask_model,
    ask_model_with_fallback,
    ask_model_with_manual_search,
    ask_model_with_search_fallback,
    ask_model_with_tools,
)
from quota_manager import get_model_quotas, is_quota_available
from tool_manager import get_available_tools

import tools_calculator  # noqa: F401 - registra la herramienta al importar.
import tools_web_search  # noqa: F401 - registra la herramienta al importar.


logger = logging.getLogger(__name__)


class ConversationNotFoundError(Exception):
    """Raised when a chat references a conversation that does not exist."""


def process_chat(
    *,
    conversation_id,
    message,
    strategy,
    provider=None,
    model=None,
    web_search=False,
    agent_mode=False,
):
    """Coordinate model selection, context, provider call, and persistence."""
    agent_candidates = None
    if strategy == "manual":
        if not provider or not model:
            raise ValueError("La estrategia manual requiere proveedor y modelo.")

        quota = get_model_quotas().get(f"{provider}/{model}")
        if not is_quota_available(quota):
            raise ValueError(
                f"El modelo {provider}/{model} alcanzó "
                "su límite local configurado."
            )
    elif agent_mode:
        general_candidates = get_model_candidates(
            capability="general",
            strategy=strategy,
        )
        agent_candidates = [
            candidate
            for candidate in general_candidates
            if candidate.get("supports_tools")
        ]
        selected = (agent_candidates or general_candidates)[0]
        provider = selected["provider"]
        model = selected["model"]
    else:
        selected = select_model(capability="general", strategy=strategy)
        provider = selected["provider"]
        model = selected["model"]

    if (
        agent_mode
        and strategy == "manual"
        and not supports_tools(provider, model)
    ):
        raise ValueError(
            f"El modelo {provider}/{model} no admite herramientas. "
            "Selecciona un modelo compatible o usa selección automática."
        )
    if agent_mode and not TAVILY_API_KEY:
        raise ValueError(
            "El modo agente requiere configurar TAVILY_API_KEY "
            "para investigar en la web."
        )

    if conversation_id is None:
        messages = []
    else:
        if get_conversation(conversation_id) is None:
            raise ConversationNotFoundError(conversation_id)
        messages = get_conversation_messages(conversation_id)

    # Search results are presentation metadata; providers only receive chat fields.
    messages = [
        {"role": item["role"], "content": item.get("content", "")}
        for item in messages
    ]

    tool_context = [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in get_available_tools()
    ]
    tool_context.append({"type": "browser_search"})

    agent_instruction = None
    if agent_mode:
        agent_instruction = {
            "role": "system",
            "content": (
                "MODO AGENTE DE INVESTIGACIÓN: trabaja activamente en el objetivo "
                "del usuario. Desglósalo en subtareas, usa búsqueda web para "
                "comprobar hechos y fuentes actuales, compara evidencia y termina "
                "con un resultado completo y accionable. No afirmes que terminaste "
                "si quedan partes importantes; explica cualquier límite o dato que "
                "no hayas podido verificar. Incluye enlaces de las fuentes usadas."
            ),
        }

    fixed_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
        {
            "role": "system",
            "content": json.dumps(tool_context, ensure_ascii=False),
        },
    ]
    if agent_instruction:
        fixed_messages.append(agent_instruction)

    conversation_history = messages

    def build_messages(selected_provider, selected_model):
        result_messages = trim_conversation_history(
            conversation_history,
            max_characters=MAX_CONTEXT_CHARACTERS - len(message),
            max_tokens=get_input_token_budget(
                get_context_window(selected_provider, selected_model)
            ),
            model=f"{selected_provider}/{selected_model}",
            fixed_messages=fixed_messages,
        )
        if agent_instruction:
            result_messages.insert(0, agent_instruction)
        result_messages.append({"role": "user", "content": message})
        return result_messages

    messages = build_messages(provider, model)

    search_results = []
    if agent_mode:
        candidates_to_try = (
            agent_candidates
            if agent_candidates is not None
            else [{"provider": provider, "model": model}]
        )
        result = None
        failures = []

        logger.info(
            "Candidatos del agente con herramientas: %s",
            [
                f"{candidate['provider']}/{candidate['model']}"
                for candidate in candidates_to_try
            ],
        )

        for candidate in candidates_to_try:
            provider = candidate["provider"]
            model = candidate["model"]
            candidate_messages = build_messages(provider, model)
            try:
                result = ask_model_with_tools(
                    provider=provider,
                    model=model,
                    messages=candidate_messages,
                    tool_names=["calculator", "web_search"],
                    max_iterations=12,
                    return_metadata=True,
                )
                break
            except Exception as error:
                failures.append(f"{provider}/{model}: {error}")
                logger.warning(
                    "El modelo del agente falló; se probará el siguiente "
                    "candidato (%s / %s): %s",
                    provider,
                    model,
                    error,
                )

        if result is None:
            attempted = "; ".join(failures)
            if agent_candidates is None:
                raise RuntimeError(
                    f"Falló el modelo manual {provider}/{model}: {attempted}"
                )

            excluded_models = [
                (candidate["provider"], candidate["model"])
                for candidate in agent_candidates
            ]
            logger.warning(
                "Se agotaron los modelos con herramientas; se probará "
                "búsqueda web con los modelos generales restantes."
            )
            fallback_result = ask_model_with_search_fallback(
                messages=messages,
                strategy=strategy,
                exclude=excluded_models,
            )
            response = (
                "No se pudo completar la investigación con modelos que "
                "admiten herramientas. Esta respuesta usa búsqueda web "
                "como fallback.\n\n"
                + fallback_result["response"]["answer"]
            )
            search_results = fallback_result["response"]["results"]
            provider = fallback_result["provider"]
            model = fallback_result["model"]
        else:
            response = result["response"]
            search_results = result["results"]
    elif strategy == "manual":
        if web_search:
            result = ask_model_with_manual_search(
                provider=provider,
                model=model,
                messages=messages,
            )
            response = result["response"]["answer"]
            search_results = result["response"]["results"]
        elif supports_tools(provider, model):
            response = ask_model_with_tools(
                provider=provider,
                model=model,
                messages=messages,
                tool_names=["calculator"],
            )
        else:
            response = ask_model(
                provider=provider,
                model=model,
                messages=messages,
            )
    elif web_search:
        result = ask_model_with_search_fallback(
            messages=messages,
            strategy=strategy,
        )
        response = result["response"]["answer"]
        search_results = result["response"]["results"]
        provider = result["provider"]
        model = result["model"]
    else:
        result = ask_model_with_fallback(messages=messages, strategy=strategy)
        response = result["response"]
        provider = result["provider"]
        model = result["model"]

    title = None
    if conversation_id is None:
        title = " ".join(message.strip().split())
        if len(title) > 50:
            title = title[:47].rstrip() + "..."

    conversation_id = save_turn(
        conversation_id,
        message,
        response,
        results=search_results,
        provider=provider,
        model=model,
        title=title,
    )

    return {
        "conversation_id": conversation_id,
        "response": response,
        "results": search_results,
        "model": model,
        "provider": provider,
    }

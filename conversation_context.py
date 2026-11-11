import logging
import math

from litellm import token_counter


logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARACTERS = 24_000
MAX_CONTEXT_TURNS = 12
MAX_CONTEXT_TOKENS = 8_192
CONTEXT_OVERHEAD_RESERVE = 2_048


def count_message_tokens(messages, model):
    try:
        return token_counter(model=model, messages=messages)
    except Exception:
        logger.debug(
            "No se pudo determinar el tokenizador de %s; se usa una estimación conservadora.",
            model,
            exc_info=True
        )
        text = "".join(message.get("content") or "" for message in messages)
        return math.ceil(len(text.encode("utf-8")) / 2)


def trim_conversation_history(
    messages,
    max_characters,
    model,
    fixed_messages=None,
    max_tokens=MAX_CONTEXT_TOKENS
):
    """Keep recent complete turns within character and token budgets."""
    fixed_token_count = count_message_tokens(fixed_messages or [], model)
    available_tokens = (
        max_tokens - CONTEXT_OVERHEAD_RESERVE - fixed_token_count
    )
    if available_tokens < 0:
        raise ValueError(
            "El mensaje actual supera el presupuesto de contexto disponible."
        )
    if max_characters <= 0:
        return []

    recent_turns = []
    total_characters = 0
    total_tokens = 0
    cursor = len(messages)

    while cursor >= 2 and len(recent_turns) < MAX_CONTEXT_TURNS:
        turn = messages[cursor - 2:cursor]
        if turn[0].get("role") != "user" or turn[1].get("role") != "assistant":
            cursor -= 1
            continue

        turn_characters = sum(
            len(message.get("content") or "")
            for message in turn
        )
        turn_tokens = count_message_tokens(turn, model)

        if (
            total_characters + turn_characters > max_characters
            or total_tokens + turn_tokens > available_tokens
        ):
            break

        recent_turns.insert(0, turn)
        total_characters += turn_characters
        total_tokens += turn_tokens
        cursor -= 2

    return [message for turn in recent_turns for message in turn]

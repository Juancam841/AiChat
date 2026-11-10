MAX_CONTEXT_CHARACTERS = 24_000
MAX_CONTEXT_TURNS = 12


def trim_conversation_history(messages, max_characters):
    """Keep the newest complete user/assistant turns within the context budget."""
    if max_characters <= 0:
        return []

    recent_turns = []
    total_characters = 0
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

        if total_characters + turn_characters > max_characters:
            break

        recent_turns.insert(0, turn)
        total_characters += turn_characters
        cursor -= 2

    return [message for turn in recent_turns for message in turn]

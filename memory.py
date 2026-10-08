
MAX_HISTORY_MESSAGES = 12
MAX_MESSAGE_LENGTH = 6000


def build_messages(history, new_message):
    messages = []

    if isinstance(history, list):
        for item in history[-MAX_HISTORY_MESSAGES:]:
            if not isinstance(item, dict):
                continue

            role = item.get("role")
            content = item.get("content")

            if role not in ("user", "assistant"):
                continue

            if not isinstance(content, str) or not content.strip():
                continue

            messages.append({
                "role": role,
                "content": content[:MAX_MESSAGE_LENGTH],
            })

    messages.append({
        "role": "user",
        "content": new_message[:MAX_MESSAGE_LENGTH],
    })

    return messages[-(MAX_HISTORY_MESSAGES + 1):]

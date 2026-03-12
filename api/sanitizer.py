import re
from typing import Any


# Fields that should never appear in webhook payloads
BLOCKED_KEYS = {
    "password", "passwd", "secret", "token",
    "api_key", "apikey", "private_key", "ssn",
    "credit_card", "card_number", "cvv"
}

# Pattern to detect script injection
SCRIPT_PATTERN = re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL)


def sanitize_payload(payload: Any, depth: int = 0) -> Any:
    if depth > 10:
        return {}

    if isinstance(payload, dict):
        sanitized = {}
        for key, value in payload.items():
            if key.lower() in BLOCKED_KEYS:
                continue
            sanitized[key] = sanitize_payload(value, depth + 1)
        return sanitized

    if isinstance(payload, list):
        return [sanitize_payload(item, depth + 1) for item in payload]

    if isinstance(payload, str):
        return SCRIPT_PATTERN.sub("", payload)

    return payload

REDACTED_PLACEHOLDER = "[REDACTED]"
SENSITIVE_KEY_FRAGMENTS = ("password", "token", "secret")
SENSITIVE_KEYS = frozenset({"access", "refresh"})


def is_sensitive_key(key):
    normalized_key = str(key).lower()
    if normalized_key in SENSITIVE_KEYS:
        return True
    return any(fragment in normalized_key for fragment in SENSITIVE_KEY_FRAGMENTS)


def redact_sensitive_values(payload):
    if isinstance(payload, dict):
        return {key: redact_entry(key, value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [redact_sensitive_values(item) for item in payload]
    return payload


def redact_entry(key, value):
    if is_sensitive_key(key):
        return REDACTED_PLACEHOLDER
    return redact_sensitive_values(value)

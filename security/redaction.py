from django.conf import settings

REDACTED_PLACEHOLDER = "[REDACTED]"
SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "passwd",
    "token",
    "secret",
    "apikey",
    "authorization",
    "credential",
    "privatekey",
    "recoverycode",
)
# Short words match whole keys only: as fragments, "pin" would also hide "shipping".
SENSITIVE_KEYS = frozenset(
    {"otp", "pin", "cvv", "cvc", "cardnumber", "ssn", "access", "refresh"}
)


def normalize_key(key):
    return str(key).lower().replace("-", "").replace("_", "")


def extra_sensitive_keys():
    return {normalize_key(key) for key in settings.AUDIT_EXTRA_SENSITIVE_KEYS}


def is_sensitive_key(key):
    normalized_key = normalize_key(key)
    if normalized_key in SENSITIVE_KEYS or normalized_key in extra_sensitive_keys():
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

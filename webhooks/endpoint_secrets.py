import secrets

SECRET_BYTES = 32


def generate_webhook_secret() -> str:
    return secrets.token_urlsafe(SECRET_BYTES)

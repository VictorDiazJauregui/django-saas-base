from urllib.parse import parse_qs, urlsplit

from django.test import override_settings

FRONTEND = "https://app.example.com"
RESET_URL = f"{FRONTEND}/reset-password?uid={{uid}}&token={{token}}"
VERIFICATION_URL = f"{FRONTEND}/verify-email?uid={{uid}}&token={{token}}"
FAST_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


def with_account_links():
    return override_settings(
        FRONTEND_PASSWORD_RESET_URL=RESET_URL,
        FRONTEND_EMAIL_VERIFICATION_URL=VERIFICATION_URL,
        EMAIL_SEND_IN_BACKGROUND=False,
        PASSWORD_HASHERS=FAST_HASHERS,
    )


def find_link(message):
    words = message.body.split()
    return next(word for word in words if word.startswith(FRONTEND))


def read_link_parameters(message):
    query = parse_qs(urlsplit(find_link(message)).query)
    return {"uid": query["uid"][0], "token": query["token"][0]}

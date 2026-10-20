import re
from importlib.util import find_spec

from django.core.exceptions import ImproperlyConfigured

ANYMAIL_PREFIX = "ANYMAIL_"
PROVIDER_NAME = re.compile(r"^[a-z][a-z_]*$")
# Modules of anymail.backends that hold shared code, not a provider.
NON_PROVIDER_MODULES = frozenset({"base", "base_requests"})
BOOLEAN_VALUES = {"true": True, "false": False}


def build_provider_backend(provider):
    return f"anymail.backends.{provider}.EmailBackend"


def is_known_provider(provider):
    if not PROVIDER_NAME.match(provider) or provider in NON_PROVIDER_MODULES:
        return False
    return find_spec(f"anymail.backends.{provider}") is not None


def validate_email_provider(provider, email_url):
    if not provider:
        return provider
    if not is_known_provider(provider):
        raise ImproperlyConfigured(
            f"EMAIL_PROVIDER={provider!r} is not an anymail provider. Use one of the "
            "names in https://anymail.dev/en/stable/esps/, such as mailgun or resend."
        )
    if email_url:
        raise ImproperlyConfigured(
            "Set EMAIL_URL or EMAIL_PROVIDER, not both: EMAIL_PROVIDER sends through "
            "the provider's API and EMAIL_URL through SMTP."
        )
    return provider


# Values come from the environment as text: only true and false need a type of their own.
def read_anymail_settings(environment):
    return {
        name.removeprefix(ANYMAIL_PREFIX): BOOLEAN_VALUES.get(value.lower(), value)
        for name, value in environment.items()
        if name.startswith(ANYMAIL_PREFIX)
    }

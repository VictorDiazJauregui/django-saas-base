import os
from collections.abc import Callable
from dataclasses import dataclass

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import get_connection

from core.environment import is_deployed

# Public placeholders copied from .env.example, not secrets.
EXAMPLE_SECRET_KEY = "change-me-with-a-generated-secret-key"  # noqa: S105
EXAMPLE_DB_PASSWORD = "change-me"  # noqa: S105
EXAMPLE_ADMIN_PASSWORD = "change-me"  # noqa: S105


@dataclass(frozen=True)
class ExampleValue:
    variable: str
    example: str
    check_number: int
    read_current: Callable[[], str | None]


EXAMPLE_VALUES = (
    ExampleValue("SECRET_KEY", EXAMPLE_SECRET_KEY, 1, lambda: settings.SECRET_KEY),
    ExampleValue(
        "DB_PASSWORD",
        EXAMPLE_DB_PASSWORD,
        2,
        lambda: settings.DATABASES["default"]["PASSWORD"],
    ),
    # create_admin_auto reads it from the environment; it is not a Django setting.
    ExampleValue(
        "ADMIN_PASSWORD",
        EXAMPLE_ADMIN_PASSWORD,
        3,
        lambda: os.environ.get("ADMIN_PASSWORD"),
    ),
)


def build_example_value_message(value):
    deployed = is_deployed(settings.ENVIRONMENT)
    message_class = Error if deployed else Warning
    level_letter = "E" if deployed else "W"
    return message_class(
        f"{value.variable} still has the value from .env.example.",
        hint=f"Set your own {value.variable} in .env.",
        id=f"core.{level_letter}{value.check_number:03d}",
    )


# Errors stop runserver, migrate and check --deploy, so staging and prod can't start
# with a value anyone can read in the public repository.
@register(Tags.security)
def check_example_values(app_configs, **kwargs):
    return [
        build_example_value_message(value)
        for value in EXAMPLE_VALUES
        if value.read_current() == value.example
    ]


NON_DELIVERING_EMAIL_BACKENDS = frozenset(
    {
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
        "django.core.mail.backends.locmem.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
        "anymail.backends.console.EmailBackend",
        "anymail.backends.test.EmailBackend",
    }
)


# A deployment without EMAIL_URL starts fine and only prints the emails to its log: password
# resets and verifications never reach anyone, and nobody notices.
@register()
def check_email_backend(app_configs, **kwargs):
    if not is_deployed(settings.ENVIRONMENT):
        return []
    if settings.EMAIL_BACKEND not in NON_DELIVERING_EMAIL_BACKENDS:
        return []
    return [
        Warning(
            "EMAIL_URL does not deliver emails: password reset and verification "
            "emails will not reach anyone.",
            hint="Set EMAIL_URL or EMAIL_PROVIDER in .env.",
            id="core.W004",
        )
    ]


# anymail reads its settings when it opens a connection, the first time an email goes out:
# a missing API key would only show up as a failed password reset in the log.
@register()
def check_email_provider_settings(app_configs, **kwargs):
    if not settings.EMAIL_BACKEND.startswith("anymail."):
        return []
    try:
        get_connection()
    except ImproperlyConfigured as error:
        return [
            Error(
                f"EMAIL_PROVIDER is incomplete: {error}",
                hint="Set the ANYMAIL_* variables your provider needs in .env.",
                id="core.E004",
            )
        ]
    return []

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SecurityConfig(AppConfig):
    name = "security"
    verbose_name = _("Security")

    def ready(self):
        from . import api_key_schema, signals  # noqa: F401

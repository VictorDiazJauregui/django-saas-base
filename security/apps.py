from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SecurityConfig(AppConfig):
    name = "security"
    verbose_name = _("Security")

    def ready(self):
        from . import signals  # noqa: F401

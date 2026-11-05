from django.apps import AppConfig
from django.urls import register_converter
from django.utils.translation import gettext_lazy as _

from .url_converters import ORGANIZATION_CONVERTER_NAME, OrganizationReferenceConverter


class OrganizationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "organizations"
    verbose_name = _("Organizations")

    def ready(self):
        from organizations import api_key_schema, checks  # noqa: F401 - registers them

        register_converter(OrganizationReferenceConverter, ORGANIZATION_CONVERTER_NAME)

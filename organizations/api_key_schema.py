from django.utils.translation import gettext_lazy as _
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class OrganizationApiKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "organizations.authentication.OrganizationApiKeyAuthentication"
    name = "organizationApiKeyAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": _(
                "Api-Key <key> with a key that starts with org_. Only with "
                "TENANCY_ENABLED=True and API_KEYS_ENABLED=True; an admin of the "
                "organization creates it in /api/v1/organizations/<organization>/api-keys/."
            ),
        }

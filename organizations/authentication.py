from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from security.api_keys import INVALID_API_KEY_CODE, INVALID_API_KEY_MESSAGE
from security.authentication import API_KEY_KEYWORD

from .api_key_actor import OrganizationApiKeyActor
from .models import OrganizationApiKey
from .organization_api_keys import (
    authenticate_organization_api_key,
    is_organization_api_key,
)


def organization_api_keys_enabled() -> bool:
    return settings.TENANCY_ENABLED and settings.API_KEYS_ENABLED


def read_api_key_header(request: Request) -> str | None:
    parts = get_authorization_header(request).split()
    if len(parts) != 2 or parts[0].lower() != API_KEY_KEYWORD:
        return None
    return parts[1].decode(errors="replace")


# Listed before the personal key class, which would refuse any key it doesn't know. Keys
# without the organization marker are left to it untouched.
class OrganizationApiKeyAuthentication(BaseAuthentication):
    def authenticate(
        self, request: Request
    ) -> tuple[OrganizationApiKeyActor, OrganizationApiKey] | None:
        raw_key = read_api_key_header(request)
        if raw_key is None or not is_organization_api_key(raw_key):
            return None
        if not organization_api_keys_enabled():
            raise AuthenticationFailed(INVALID_API_KEY_MESSAGE, INVALID_API_KEY_CODE)
        api_key = authenticate_organization_api_key(raw_key)
        return OrganizationApiKeyActor(api_key), api_key

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .api_keys import (
    INVALID_API_KEY_CODE,
    INVALID_API_KEY_MESSAGE,
    authenticate_api_key,
)

API_KEY_KEYWORD = b"api-key"


# Refusing here, like an inactive account, makes an unverified login look exactly like a wrong
# password: a different answer would tell whoever registered an email whether it already
# had an account.
class VerifiedEmailModelBackend(ModelBackend):
    def user_can_authenticate(self, user):
        if not super().user_can_authenticate(user):
            return False
        return user.is_email_verified or not settings.REQUIRE_EMAIL_VERIFICATION


# Always listed in the settings and switched off here: DRF copies the authentication classes
# into each view when it is defined, so a list built from the flag could not change later.
class ApiKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        if not settings.API_KEYS_ENABLED:
            return None
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != API_KEY_KEYWORD:
            return None
        if len(parts) != 2:
            raise AuthenticationFailed(INVALID_API_KEY_MESSAGE, INVALID_API_KEY_CODE)
        api_key = authenticate_api_key(parts[1].decode(errors="replace"))
        return api_key.user, api_key

    def authenticate_header(self, request):
        return "Api-Key"

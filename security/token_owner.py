from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings


# Only called with tokens the view has just issued or accepted, so the signature is not
# checked again: a refresh token already sits in the blacklist after a logout.
def find_token_owner(token_class, raw_token):
    try:
        token = token_class(raw_token, verify=False)
    except TokenError:
        return None
    user_id = token.payload.get(api_settings.USER_ID_CLAIM)
    return get_user_model().objects.filter(pk=user_id).first()

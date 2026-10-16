from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _

INVALID_LINK_MESSAGE = _("Invalid or expired link.")


def encode_user_id(user):
    return urlsafe_base64_encode(force_bytes(user.pk))


def find_user_by_encoded_id(encoded_id):
    try:
        user_id = force_str(urlsafe_base64_decode(encoded_id))
        return get_user_model().objects.filter(pk=user_id).first()
    except (ValueError, ValidationError):
        return None


# str.replace and not str.format: any other brace in the frontend URL stays as it is.
def build_frontend_link(url_template, user, token):
    return url_template.replace("{uid}", encode_user_id(user)).replace("{token}", token)

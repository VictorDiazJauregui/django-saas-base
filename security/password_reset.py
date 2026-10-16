from axes.utils import reset as reset_failed_logins
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator

from core.emails import send_templated_email

from .frontend_links import build_frontend_link, find_user_by_encoded_id
from .password_change import set_new_password

RESET_EMAIL_TEMPLATE = "security/emails/password_reset"


def find_resettable_user(email):
    user = get_user_model().objects.filter(email__iexact=email, is_active=True).first()
    if user is None or not user.has_usable_password():
        return None
    return user


def request_password_reset(email):
    user = find_resettable_user(email)
    if user is None:
        return
    token = default_token_generator.make_token(user)
    context = {
        "reset_url": build_frontend_link(
            settings.FRONTEND_PASSWORD_RESET_URL, user, token
        ),
        "timeout_minutes": settings.PASSWORD_RESET_TIMEOUT // 60,
    }
    send_templated_email(RESET_EMAIL_TEMPLATE, user.email, context)


def find_user_for_reset(encoded_id, token):
    user = find_user_by_encoded_id(encoded_id)
    if user is None or not default_token_generator.check_token(user, token):
        return None
    return user


# Whoever controls the email may reset the password, so the failed logins that locked the
# account stop counting too.
def complete_password_reset(user, new_password):
    set_new_password(user, new_password)
    reset_failed_logins(username=user.email)

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction

from core.emails import send_templated_email

from .account_events import USER_EMAIL_VERIFIED, emit_account_event
from .frontend_links import build_frontend_link, find_user_by_encoded_id

VERIFICATION_SALT = "security.email_verification"
VERIFICATION_EMAIL_TEMPLATE = "security/emails/email_verification"


# Django's reset tokens share one lifetime for the whole project; a signed value carries its
# own, so a verification link can outlive a reset link.
def build_verification_token(user):
    return signing.dumps([str(user.pk), user.email], salt=VERIFICATION_SALT)


def is_valid_verification_token(user, token):
    max_age = settings.EMAIL_VERIFICATION_TIMEOUT
    try:
        signed = signing.loads(token, salt=VERIFICATION_SALT, max_age=max_age)
    except signing.BadSignature:
        return False
    return signed == [str(user.pk), user.email]


def is_pending_verification(user):
    return user.is_active and not user.is_email_verified


def send_verification_email(user):
    token = build_verification_token(user)
    context = {
        "verification_url": build_frontend_link(
            settings.FRONTEND_EMAIL_VERIFICATION_URL, user, token
        ),
        "timeout_hours": settings.EMAIL_VERIFICATION_TIMEOUT // 3600,
    }
    send_templated_email(VERIFICATION_EMAIL_TEMPLATE, user.email, context)


def resend_verification(email):
    if not settings.REQUIRE_EMAIL_VERIFICATION:
        return
    user = get_user_model().objects.filter(email__iexact=email).first()
    if user is None or not is_pending_verification(user):
        return
    send_verification_email(user)


def find_user_to_verify(encoded_id, token):
    user = find_user_by_encoded_id(encoded_id)
    if user is None or not is_pending_verification(user):
        return None
    if not is_valid_verification_token(user, token):
        return None
    return user


@transaction.atomic
def mark_email_verified(user):
    user.is_email_verified = True
    user.save(update_fields=["is_email_verified"])
    emit_account_event(USER_EMAIL_VERIFIED, user)

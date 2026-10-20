from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction

from core.emails import send_templated_email

from .account_events import USER_REGISTERED, emit_account_event
from .email_verification import send_verification_email

DUPLICATE_REGISTRATION_TEMPLATE = "security/emails/duplicate_registration"


# The answer is the same whether the email had an account or not: the owner learns about the
# attempt by email, and whoever registered learns nothing.
def register_account(registration):
    if get_user_model().objects.is_email_taken(registration["email"]):
        warn_existing_owner(registration)
        return
    try:
        with transaction.atomic():
            user = create_account(registration)
    except IntegrityError:
        warn_existing_owner(registration)
        return
    if settings.REQUIRE_EMAIL_VERIFICATION:
        send_verification_email(user)


def create_account(registration):
    verified = not settings.REQUIRE_EMAIL_VERIFICATION
    user = get_user_model().objects.create_user(
        **registration, is_email_verified=verified
    )
    emit_account_event(USER_REGISTERED, user)
    return user


# Hashing the submitted password costs what creating the account costs, so a duplicate takes
# as long to answer as a new email.
def warn_existing_owner(registration):
    make_password(registration["password"])
    send_templated_email(DUPLICATE_REGISTRATION_TEMPLATE, registration["email"], {})

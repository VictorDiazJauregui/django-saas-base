from enum import StrEnum

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import CommandError


class SuperuserBootstrapError(CommandError):
    pass


class BootstrapOutcome(StrEnum):
    CREATED = "created"
    ALREADY_EXISTS = "already exists"
    UPDATED = "password updated"
    UNCHANGED = "password unchanged"


def find_user(email):
    return get_user_model().objects.filter(email__iexact=email).first()


def validate_superuser_password(email, password):
    # An unsaved user lets the similarity validator compare the password with the email.
    candidate = get_user_model()(email=email)
    try:
        validate_password(password, user=candidate)
    except ValidationError as error:
        reasons = " ".join(error.messages)
        raise SuperuserBootstrapError(
            f"ADMIN_PASSWORD was rejected: {reasons}"
        ) from error


def ensure_is_superuser(user):
    if not user.is_superuser:
        raise SuperuserBootstrapError(
            f'"{user.email}" already exists but is not a superuser. Promote it from the '
            "admin or set another ADMIN_EMAIL."
        )


def create_superuser(email, password):
    user_model = get_user_model()
    normalized_email = user_model.objects.normalize_email(email)
    validate_superuser_password(normalized_email, password)
    user_model.objects.create_superuser(email=normalized_email, password=password)
    return BootstrapOutcome.CREATED


def ensure_superuser(email, password):
    user = find_user(email)
    if user is None:
        return create_superuser(email, password)
    ensure_is_superuser(user)
    return BootstrapOutcome.ALREADY_EXISTS


def rotate_superuser_password(email, password):
    user = find_user(email)
    if user is None:
        return create_superuser(email, password)
    ensure_is_superuser(user)
    if user.check_password(password):
        return BootstrapOutcome.UNCHANGED
    validate_superuser_password(user.email, password)
    user.set_password(password)
    user.save(update_fields=["password"])
    return BootstrapOutcome.UPDATED

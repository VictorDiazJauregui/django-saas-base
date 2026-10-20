import hashlib
import logging
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException, Throttled

from .models import RecoveryCode, TotpDevice
from .security_events import log_second_factor_failed
from .token_pair import issue_token_pair
from .totp import (
    TotpSecretUnreadable,
    build_provisioning_uri,
    decrypt_secret,
    encrypt_secret,
    find_matching_step,
    generate_secret,
    is_well_formed_code,
)

logger = logging.getLogger(__name__)

RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_BYTES = 8
MFA_TOKEN_SALT = (
    "security.two_factor.mfa_token"  # noqa: S105 - a namespace, not a secret
)
MFA_TOKEN_MAX_AGE_SECONDS = 300
MAX_CODE_FAILURES = 5
CODE_FAILURE_WINDOW_SECONDS = 300


class TotpAlreadyEnabled(APIException):
    status_code = 409
    default_detail = _("Two-factor authentication is already on.")
    default_code = "totp_already_enabled"


class TotpNotEnabled(APIException):
    status_code = 409
    default_detail = _("Two-factor authentication is off.")
    default_code = "totp_not_enabled"


# Not an AuthenticationFailed: DRF turns that one into a 403 on a view without authentication
# classes, and the second step has none.
class InvalidMfaToken(APIException):
    status_code = 401
    default_detail = _("The login expired or is not valid. Log in again.")
    default_code = "invalid_mfa_token"


class TooManyCodeAttempts(Throttled):
    default_detail = _("Too many wrong codes.")
    default_code = "too_many_code_attempts"


def find_confirmed_device(user):
    return TotpDevice.objects.filter(user=user, confirmed_at__isnull=False).first()


def requires_second_factor(user):
    return settings.TOTP_ENABLED and find_confirmed_device(user) is not None


def start_totp_setup(user):
    if find_confirmed_device(user) is not None:
        raise TotpAlreadyEnabled
    secret = generate_secret()
    TotpDevice.objects.update_or_create(
        user=user,
        defaults={"encrypted_secret": encrypt_secret(secret), "last_used_step": None},
    )
    return {"secret": secret, "otpauth_uri": build_provisioning_uri(secret, user.email)}


def find_pending_device(user):
    return TotpDevice.objects.filter(user=user, confirmed_at__isnull=True).first()


@transaction.atomic
def confirm_totp_setup(device):
    device.confirmed_at = timezone.now()
    device.save(update_fields=["confirmed_at", "updated_at"])
    return replace_recovery_codes(device.user)


def replace_recovery_codes(user):
    codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    RecoveryCode.objects.filter(user=user).delete()
    RecoveryCode.objects.bulk_create(
        RecoveryCode(user=user, code_hash=hash_recovery_code(code)) for code in codes
    )
    return codes


def generate_recovery_code():
    hex_code = secrets.token_hex(RECOVERY_CODE_BYTES)
    return "-".join(hex_code[index : index + 4] for index in range(0, len(hex_code), 4))


def normalize_recovery_code(code):
    return "".join(code.split()).replace("-", "").lower()


# 64 random bits per code: SHA-256 is enough, and the lookup goes straight to the row.
def hash_recovery_code(code):
    return hashlib.sha256(normalize_recovery_code(code).encode()).hexdigest()


def count_unused_recovery_codes(user):
    return RecoveryCode.objects.filter(user=user, used_at__isnull=True).count()


@transaction.atomic
def disable_totp_for(users):
    TotpDevice.objects.filter(user__in=users).delete()
    RecoveryCode.objects.filter(user__in=users).delete()


def disable_totp(user):
    disable_totp_for([user])


def accept_totp_code(device, otp):
    try:
        secret = decrypt_secret(device.encrypted_secret)
    except TotpSecretUnreadable:
        logger.error(
            "Can't read the TOTP secret of user %s: TOTP_ENCRYPTION_KEY changed.",
            device.user_id,
            extra={"event": "totp_secret_unreadable", "user_id": str(device.user_id)},
        )
        return False
    step = find_matching_step(secret, otp, device.last_used_step)
    return step is not None and claim_step(device, step)


# The conditional update makes two requests with the same code race for one row: only the
# first one changes it.
def claim_step(device, step):
    not_used_yet = Q(last_used_step__isnull=True) | Q(last_used_step__lt=step)
    claimed = TotpDevice.objects.filter(not_used_yet, pk=device.pk).update(
        last_used_step=step
    )
    return claimed == 1


def accept_recovery_code(user, code):
    unused = RecoveryCode.objects.filter(
        user=user, code_hash=hash_recovery_code(code), used_at__isnull=True
    )
    return unused.update(used_at=timezone.now()) == 1


def failure_cache_key(user):
    return f"security:two_factor:failures:{user.pk}"


def raise_if_code_attempts_exceeded(user):
    if cache.get(failure_cache_key(user), 0) >= MAX_CODE_FAILURES:
        raise TooManyCodeAttempts(wait=CODE_FAILURE_WINDOW_SECONDS)


def record_code_failure(user):
    key = failure_cache_key(user)
    cache.add(key, 0, CODE_FAILURE_WINDOW_SECONDS)
    cache.incr(key)


def issue_mfa_token(user):
    return signing.dumps(str(user.pk), salt=MFA_TOKEN_SALT)


def find_mfa_token_owner(mfa_token):
    try:
        user_id = signing.loads(
            mfa_token, salt=MFA_TOKEN_SALT, max_age=MFA_TOKEN_MAX_AGE_SECONDS
        )
    except signing.BadSignature as error:
        raise InvalidMfaToken from error
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None or not requires_second_factor(user):
        raise InvalidMfaToken
    return user


def accept_factor(user, otp=None, recovery_code=None):
    if recovery_code:
        return accept_recovery_code(user, recovery_code)
    device = find_confirmed_device(user)
    return device is not None and accept_totp_code(device, otp)


# Every code check counts against the same limit, so a stolen password or session can't try
# the million possible codes.
def run_code_attempt(user, attempt):
    raise_if_code_attempts_exceeded(user)
    if attempt():
        cache.delete(failure_cache_key(user))
        return True
    record_code_failure(user)
    log_second_factor_failed(user)
    return False


def verify_second_factor(user, otp=None, recovery_code=None):
    return run_code_attempt(user, lambda: accept_factor(user, otp, recovery_code))


def verify_setup_code(device, otp):
    return run_code_attempt(device.user, lambda: accept_totp_code(device, otp))


# The password was right: a user with two-factor authentication gets a short-lived token for
# the second step instead of the tokens.
def build_login_answer(user):
    if requires_second_factor(user):
        return {"mfa_required": True, "mfa_token": issue_mfa_token(user)}
    return issue_token_pair(user)


# The admin has one field for both: six digits are a code of the app, anything else a
# recovery code.
def verify_typed_code(user, typed_code):
    if is_well_formed_code(typed_code):
        return verify_second_factor(user, otp=typed_code)
    return verify_second_factor(user, recovery_code=typed_code)

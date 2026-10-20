import hmac

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.utils import timezone

# One step before and one after the current one, for clocks that drift up to 30 seconds.
ACCEPTED_STEP_OFFSETS = (-1, 0, 1)
CODE_LENGTH = 6


class TotpSecretUnreadable(Exception):
    """The secret was encrypted with a TOTP_ENCRYPTION_KEY that is no longer configured."""


def build_cipher():
    return Fernet(settings.TOTP_ENCRYPTION_KEY)


def generate_secret():
    return pyotp.random_base32()


def encrypt_secret(secret):
    return build_cipher().encrypt(secret.encode()).decode()


def decrypt_secret(encrypted_secret):
    try:
        return build_cipher().decrypt(encrypted_secret.encode()).decode()
    except InvalidToken as error:
        raise TotpSecretUnreadable from error


def build_provisioning_uri(secret, email):
    issuer = settings.TOTP_ISSUER or None
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def is_well_formed_code(otp):
    return len(otp) == CODE_LENGTH and otp.isdigit()


def find_matching_step(secret, otp, last_used_step):
    totp = pyotp.TOTP(secret)
    current_step = totp.timecode(timezone.now())
    for step in (current_step + offset for offset in ACCEPTED_STEP_OFFSETS):
        if last_used_step is not None and step <= last_used_step:
            continue
        if hmac.compare_digest(totp.generate_otp(step), otp):
            return step
    return None

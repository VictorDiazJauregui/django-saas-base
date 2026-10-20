import pyotp
from cryptography.fernet import Fernet
from django.test import override_settings
from django.urls import reverse

from security.models import TotpDevice

from .user_factory import DEFAULT_EMAIL, DEFAULT_PASSWORD

TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


def with_two_factor(enabled=True):
    return override_settings(
        TOTP_ENABLED=enabled,
        TOTP_ENCRYPTION_KEY=TEST_ENCRYPTION_KEY,
        TOTP_ISSUER="Acme",
    )


def current_code(secret):
    return pyotp.TOTP(secret).now()


# Each code works once: the tests that need a second one let the device forget the last.
def forget_last_code(user):
    TotpDevice.objects.filter(user=user).update(last_used_step=None)


def enable_two_factor(client, user):
    client.force_authenticate(user)
    secret = client.post(reverse("security:totp_setup")).data["secret"]
    confirmation = client.post(
        reverse("security:totp_confirm"), {"otp": current_code(secret)}, format="json"
    )
    client.force_authenticate(None)
    forget_last_code(user)
    return secret, confirmation.data["recovery_codes"]


def log_in(client, email=DEFAULT_EMAIL, password=DEFAULT_PASSWORD):
    return client.post(
        reverse("security:login"), {"email": email, "password": password}, format="json"
    )

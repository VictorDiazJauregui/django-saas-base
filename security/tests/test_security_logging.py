import logging

from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from core.log_formatters import JsonFormatter

from .api_test_case import CacheResetAPITestCase
from .test_throttling import WRONG_PASSWORD, override_rates
from .user_factory import DEFAULT_EMAIL, DEFAULT_PASSWORD, create_user

LOGIN_URL = reverse("security:login")
LOGOUT_URL = reverse("security:logout")
CHANGE_URL = reverse("security:password_change")
ADMIN_LOGIN_URL = reverse("admin:login")
NEW_PASSWORD = "Changed-Passphrase-88"
CLIENT_IP = "203.0.113.9"
TEXT_FORMATTER = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")


def events(logs):
    return [record for record in logs.records if hasattr(record, "event")]


def event_named(logs, name):
    return next(record for record in events(logs) if record.event == name)


def formatted_output(logs):
    return "\n".join(
        formatter.format(record)
        for record in logs.records
        for formatter in (TEXT_FORMATTER, JsonFormatter())
    )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
@override_rates(login=None, password=None)
class SecurityLoggingTestCase(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user()
        self.secrets = [DEFAULT_PASSWORD, WRONG_PASSWORD, NEW_PASSWORD]

    def log_in(self, password=DEFAULT_PASSWORD, email=DEFAULT_EMAIL):
        payload = {"email": email, "password": password}
        response = self.client.post(
            LOGIN_URL, payload, format="json", REMOTE_ADDR=CLIENT_IP
        )
        tokens = response.data if response.status_code == status.HTTP_200_OK else {}
        self.secrets.extend(tokens.values())
        return tokens

    def assert_no_secrets(self, logs):
        output = formatted_output(logs)
        for secret in self.secrets:
            self.assertNotIn(secret, output)


class FailedLoginLoggingTests(SecurityLoggingTestCase):
    def test_failed_api_login_logs_the_email_and_ip(self):
        with self.assertLogs("security", "WARNING") as logs:
            self.log_in(WRONG_PASSWORD, email="Jane.Doe@Example.com")

        record = event_named(logs, "login_failed")
        self.assertEqual(record.levelno, logging.WARNING)
        self.assertEqual(record.email, DEFAULT_EMAIL)
        self.assertEqual(record.ip, CLIENT_IP)
        self.assertEqual(record.path, LOGIN_URL)
        self.assert_no_secrets(logs)

    def test_failed_admin_login_is_logged_too(self):
        credentials = {"username": DEFAULT_EMAIL, "password": WRONG_PASSWORD}
        with self.assertLogs("security", "WARNING") as logs:
            self.client.post(ADMIN_LOGIN_URL, credentials, REMOTE_ADDR=CLIENT_IP)

        record = event_named(logs, "login_failed")
        self.assertEqual((record.email, record.path), (DEFAULT_EMAIL, ADMIN_LOGIN_URL))
        self.assert_no_secrets(logs)

    def test_successful_login_logs_no_failure(self):
        with self.assertNoLogs("security", "WARNING"):
            self.log_in()


class LockoutLoggingTests(SecurityLoggingTestCase):
    def test_lockout_is_logged_once_with_the_email_and_ip(self):
        with self.assertLogs("security", "WARNING") as logs:
            for _ in range(5):
                self.log_in(WRONG_PASSWORD)

        lockouts = [r for r in events(logs) if r.event == "account_locked_out"]
        self.assertEqual(len(lockouts), 1)
        self.assertEqual(
            (lockouts[0].email, lockouts[0].ip), (DEFAULT_EMAIL, CLIENT_IP)
        )
        self.assert_no_secrets(logs)


class TokenRevocationLoggingTests(SecurityLoggingTestCase):
    def test_logout_logs_the_revoked_token_owner(self):
        refresh_token = self.log_in()["refresh"]
        with self.assertLogs("security", "INFO") as logs:
            self.client.post(LOGOUT_URL, {"refresh": refresh_token}, format="json")

        record = event_named(logs, "token_revoked")
        self.assertEqual(record.user_id, str(self.user.pk))
        self.assertEqual(record.reason, "logout")
        self.assert_no_secrets(logs)

    def test_rejected_logout_logs_nothing(self):
        with self.assertNoLogs("security", "INFO"):
            self.client.post(LOGOUT_URL, {"refresh": "not-a-token"}, format="json")

    def test_password_change_logs_how_many_tokens_were_revoked(self):
        self.log_in()
        access = self.log_in()["access"]
        payload = {
            "current_password": DEFAULT_PASSWORD,
            "new_password": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        }
        with self.assertLogs("security", "INFO") as logs:
            self.client.post(
                CHANGE_URL,
                payload,
                format="json",
                HTTP_AUTHORIZATION=f"Bearer {access}",
            )

        record = event_named(logs, "tokens_revoked")
        self.assertEqual((record.user_id, record.count), (str(self.user.pk), 2))
        self.assertEqual(record.reason, "password_changed")
        self.assert_no_secrets(logs)

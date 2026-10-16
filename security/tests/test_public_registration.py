from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, override_settings
from rest_framework import status

from core.tests.settings_subprocess import read_settings
from security.models import AuditLog

from .api_test_case import CacheResetAPITestCase
from .user_factory import (
    DEFAULT_EMAIL,
    DEFAULT_PASSWORD,
    build_registration_payload,
    create_user,
)

User = get_user_model()

REGISTER_URL = "/api/v1/auth/register/"
LOGIN_URL = "/api/v1/auth/login/"


class PublicRegistrationTests(CacheResetAPITestCase):
    def register(self, **overrides):
        payload = build_registration_payload(**overrides)
        return self.client.post(REGISTER_URL, payload, format="json")

    def test_registration_is_open_by_default(self):
        response = self.register()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @override_settings(ALLOW_PUBLIC_REGISTRATION=True)
    def test_registers_when_the_flag_is_on(self):
        response = self.register()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email=DEFAULT_EMAIL).exists())

    @override_settings(ALLOW_PUBLIC_REGISTRATION=False)
    def test_rejects_registration_when_the_flag_is_off(self):
        response = self.register()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["detail"], "Public registration is disabled.")
        self.assertFalse(User.objects.exists())


@override_settings(ALLOW_PUBLIC_REGISTRATION=False)
class ClosedRegistrationTests(CacheResetAPITestCase):
    def test_rejections_do_not_use_up_the_rate_limit(self):
        payloads = [
            build_registration_payload(email=f"user{i}@example.com") for i in range(6)
        ]

        statuses = [
            self.client.post(REGISTER_URL, payload, format="json").status_code
            for payload in payloads
        ]

        self.assertEqual(statuses, [status.HTTP_403_FORBIDDEN] * 6)

    def test_existing_users_can_still_log_in(self):
        create_user()
        payload = {"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD}

        response = self.client.post(LOGIN_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_records_the_rejection_in_the_audit_log(self):
        self.client.post(REGISTER_URL, build_registration_payload(), format="json")

        audit = AuditLog.objects.filter(path=REGISTER_URL).latest("timestamp")
        self.assertEqual(audit.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(audit.payload["password"], "[REDACTED]")


class PublicRegistrationSettingTests(SimpleTestCase):
    def test_is_read_from_the_environment(self):
        for raw_value, expected in (("True", True), ("False", False)):
            with self.subTest(raw_value=raw_value):
                values = read_settings(
                    ["ALLOW_PUBLIC_REGISTRATION"], ALLOW_PUBLIC_REGISTRATION=raw_value
                )

                self.assertIs(values["ALLOW_PUBLIC_REGISTRATION"], expected)

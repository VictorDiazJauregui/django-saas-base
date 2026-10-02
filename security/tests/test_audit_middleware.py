from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from security.models import AuditLog

from .user_factory import (
    DEFAULT_EMAIL,
    DEFAULT_PASSWORD,
    build_registration_payload,
    create_user,
)

REGISTER_URL = reverse("security:register")
LOGIN_URL = reverse("security:login")
REFRESH_URL = reverse("security:token_refresh")
REDACTED = "[REDACTED]"
COLUMN_MAX_LENGTH = 255
UNDECODABLE_JSON_BODY = b'{"email": "\xff"}'


class AuditTrailTests(APITestCase):
    def test_records_modifying_request(self):
        self.client.post(REGISTER_URL, build_registration_payload(), format="json")

        entry = AuditLog.objects.get()
        self.assertEqual(entry.method, "POST")
        self.assertEqual(entry.path, REGISTER_URL)
        self.assertEqual(entry.payload["email"], DEFAULT_EMAIL)

    def test_ignores_read_only_request(self):
        self.client.get(reverse("admin:login"))

        self.assertFalse(AuditLog.objects.exists())

    def test_records_client_metadata(self):
        self.client.post(
            REGISTER_URL,
            build_registration_payload(),
            format="json",
            HTTP_USER_AGENT="audit-test-agent",
            REMOTE_ADDR="198.51.100.20",
        )

        entry = AuditLog.objects.get()
        self.assertEqual(entry.user_agent, "audit-test-agent")
        self.assertEqual(entry.ip_address, "198.51.100.20")

    def test_prefers_forwarded_client_address(self):
        self.client.post(
            REGISTER_URL,
            build_registration_payload(),
            format="json",
            HTTP_X_FORWARDED_FOR="203.0.113.7,10.0.0.1",
        )

        self.assertEqual(AuditLog.objects.get().ip_address, "203.0.113.7")

    def test_links_login_to_authenticated_user(self):
        user = create_user()
        credentials = {"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD}

        self.client.post(LOGIN_URL, credentials, format="json")

        self.assertEqual(AuditLog.objects.get().user, user)

    def test_leaves_user_empty_for_anonymous_request(self):
        self.client.post(REGISTER_URL, build_registration_payload(), format="json")

        self.assertIsNone(AuditLog.objects.get().user)

    def test_stores_empty_payload_for_form_encoded_request(self):
        self.client.post(REGISTER_URL, build_registration_payload())

        self.assertEqual(AuditLog.objects.get().payload, {})


class AuditPayloadRedactionTests(APITestCase):
    def test_redacts_password_on_registration(self):
        self.client.post(REGISTER_URL, build_registration_payload(), format="json")

        self.assertEqual(AuditLog.objects.get().payload["password"], REDACTED)

    def test_redacts_password_confirmation_on_registration(self):
        self.client.post(REGISTER_URL, build_registration_payload(), format="json")

        self.assertEqual(AuditLog.objects.get().payload["password2"], REDACTED)

    def test_redacts_refresh_token(self):
        self.client.post(REFRESH_URL, {"refresh": "not-a-token"}, format="json")

        self.assertEqual(AuditLog.objects.get().payload["refresh"], REDACTED)

    def test_never_stores_the_raw_password(self):
        self.client.post(REGISTER_URL, build_registration_payload(), format="json")

        self.assertNotIn(DEFAULT_PASSWORD, str(AuditLog.objects.get().payload))


class AuditResilienceTests(APITestCase):
    def test_truncates_oversized_user_agent(self):
        oversized_user_agent = "a" * (COLUMN_MAX_LENGTH + 45)

        response = self.client.post(
            REGISTER_URL,
            build_registration_payload(),
            format="json",
            HTTP_USER_AGENT=oversized_user_agent,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(AuditLog.objects.get().user_agent), COLUMN_MAX_LENGTH)

    def test_truncates_oversized_path(self):
        oversized_path = "/" + "a" * (COLUMN_MAX_LENGTH + 45)

        response = self.client.post(oversized_path, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(len(AuditLog.objects.get().path), COLUMN_MAX_LENGTH)

    def test_survives_undecodable_json_body(self):
        response = self.client.post(
            REGISTER_URL, data=UNDECODABLE_JSON_BODY, content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(AuditLog.objects.get().payload, {})

    def test_stores_empty_payload_for_malformed_json(self):
        response = self.client.post(
            REGISTER_URL, data="{not json", content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(AuditLog.objects.get().payload, {})

    def test_falls_back_to_remote_address_for_invalid_forwarded_value(self):
        response = self.client.post(
            REGISTER_URL,
            build_registration_payload(),
            format="json",
            HTTP_X_FORWARDED_FOR="not-an-ip",
            REMOTE_ADDR="198.51.100.20",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AuditLog.objects.get().ip_address, "198.51.100.20")

    def test_ignores_whitespace_around_forwarded_address(self):
        self.client.post(
            REGISTER_URL,
            build_registration_payload(),
            format="json",
            HTTP_X_FORWARDED_FOR=" 203.0.113.7 , 10.0.0.1",
        )

        self.assertEqual(AuditLog.objects.get().ip_address, "203.0.113.7")

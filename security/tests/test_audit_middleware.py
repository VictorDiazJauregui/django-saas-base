import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from security.models import AuditLog

from .api_test_case import CacheResetAPITestCase
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
PAYLOAD_LIMIT = 256
WRONG_PASSWORD = "Wrong-Passphrase-1"


def login_body_of_size(size):
    base = {"email": DEFAULT_EMAIL, "password": WRONG_PASSWORD, "note": ""}
    filler = size - len(json.dumps(base).encode())
    return json.dumps({**base, "note": "x" * filler})


class AuditTrailTests(CacheResetAPITestCase):
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

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_ignores_forwarded_header_without_trusted_proxies(self):
        credentials = {"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD}

        self.client.post(
            LOGIN_URL,
            credentials,
            format="json",
            HTTP_X_FORWARDED_FOR="8.8.8.8",
            REMOTE_ADDR="198.51.100.20",
        )

        self.assertEqual(AuditLog.objects.get().ip_address, "198.51.100.20")

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_takes_the_entry_added_by_the_trusted_proxy(self):
        self.client.post(
            REGISTER_URL,
            build_registration_payload(),
            format="json",
            HTTP_X_FORWARDED_FOR="8.8.8.8, 203.0.113.7",
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


class AuditPayloadRedactionTests(CacheResetAPITestCase):
    def test_redacts_password_on_registration(self):
        self.client.post(REGISTER_URL, build_registration_payload(), format="json")

        self.assertEqual(AuditLog.objects.get().payload["password"], REDACTED)

    def test_redacts_password_confirmation_on_registration(self):
        self.client.post(REGISTER_URL, build_registration_payload(), format="json")

        self.assertEqual(AuditLog.objects.get().payload["password2"], REDACTED)

    def test_redacts_refresh_token(self):
        self.client.post(REFRESH_URL, {"refresh": "not-a-token"}, format="json")

        self.assertEqual(AuditLog.objects.get().payload["refresh"], REDACTED)

    def test_redacts_credential_keys_sent_to_the_api(self):
        payload = build_registration_payload(
            api_key="k-123", otp="123456", card_number="4111111111111111"
        )

        self.client.post(REGISTER_URL, payload, format="json")

        stored = AuditLog.objects.get().payload
        self.assertEqual(
            [stored["api_key"], stored["otp"], stored["card_number"]], [REDACTED] * 3
        )

    def test_never_stores_the_raw_password(self):
        self.client.post(REGISTER_URL, build_registration_payload(), format="json")

        self.assertNotIn(DEFAULT_PASSWORD, str(AuditLog.objects.get().payload))


class AuditResilienceTests(CacheResetAPITestCase):
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

    @override_settings(TRUSTED_PROXY_COUNT=1)
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

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_ignores_whitespace_around_forwarded_address(self):
        self.client.post(
            REGISTER_URL,
            build_registration_payload(),
            format="json",
            HTTP_X_FORWARDED_FOR="10.0.0.1 ,  203.0.113.7 ",
        )

        self.assertEqual(AuditLog.objects.get().ip_address, "203.0.113.7")


@override_settings(AUDIT_PAYLOAD_MAX_BYTES=PAYLOAD_LIMIT)
class AuditPayloadLimitTests(CacheResetAPITestCase):
    def post_login_body(self, body):
        return self.client.post(LOGIN_URL, data=body, content_type="application/json")

    def test_stores_a_login_body_exactly_at_the_limit(self):
        self.post_login_body(login_body_of_size(PAYLOAD_LIMIT))

        self.assertEqual(AuditLog.objects.get().payload["email"], DEFAULT_EMAIL)

    def test_stores_a_marker_one_byte_over_the_limit(self):
        response = self.post_login_body(login_body_of_size(PAYLOAD_LIMIT + 1))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            AuditLog.objects.get().payload,
            {"_omitted": "payload_too_large", "size_bytes": PAYLOAD_LIMIT + 1},
        )

    @override_settings(AUDIT_PAYLOAD_MAX_BYTES=0)
    def test_stores_every_body_without_a_limit(self):
        self.post_login_body(login_body_of_size(PAYLOAD_LIMIT * 4))

        self.assertGreater(len(AuditLog.objects.get().payload["note"]), PAYLOAD_LIMIT)


class AuditStatusCodeTests(CacheResetAPITestCase):
    def test_stores_200_for_a_correct_login(self):
        create_user()

        self.client.post(
            LOGIN_URL,
            {"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD},
            format="json",
        )

        self.assertEqual(AuditLog.objects.get().status_code, status.HTTP_200_OK)

    def test_stores_401_for_a_wrong_password(self):
        create_user()

        self.client.post(
            LOGIN_URL,
            {"email": DEFAULT_EMAIL, "password": WRONG_PASSWORD},
            format="json",
        )

        self.assertEqual(
            AuditLog.objects.get().status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_stores_400_for_an_invalid_registration(self):
        self.client.post(REGISTER_URL, {"password": "x"}, format="json")

        self.assertEqual(
            AuditLog.objects.get().status_code, status.HTTP_400_BAD_REQUEST
        )

    def test_stores_405_for_a_method_not_allowed(self):
        self.client.delete(LOGIN_URL)

        self.assertEqual(
            AuditLog.objects.get().status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    @override_settings(ROOT_URLCONF="security.tests.urls_failing_view")
    def test_stores_500_when_the_view_raises(self):
        self.client.raise_request_exception = False

        response = self.client.post("/failing/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(
            AuditLog.objects.get().status_code, status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    def test_stores_429_for_a_locked_out_login(self):
        credentials = {"email": DEFAULT_EMAIL, "password": WRONG_PASSWORD}

        for _ in range(5):
            self.client.post(LOGIN_URL, credentials, format="json")

        statuses = list(
            AuditLog.objects.order_by("pk").values_list("status_code", flat=True)
        )
        self.assertEqual(statuses, [401, 401, 401, 401, 429])


class AuditFormPayloadTests(CacheResetAPITestCase):
    def test_stores_urlencoded_fields_with_passwords_redacted(self):
        response = self.client.post(REGISTER_URL, build_registration_payload())

        stored = AuditLog.objects.get().payload
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(stored["email"], DEFAULT_EMAIL)
        self.assertEqual([stored["password"], stored["password2"]], [REDACTED] * 2)

    def test_stores_multipart_fields_without_the_file(self):
        upload = SimpleUploadedFile("avatar.png", b"\x89PNG" * 1000)
        payload = build_registration_payload(avatar=upload)

        response = self.client.post(REGISTER_URL, payload, format="multipart")

        stored = AuditLog.objects.get().payload
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(stored["first_name"], "Jane")
        self.assertNotIn("avatar", stored)
        self.assertEqual(stored["password"], REDACTED)

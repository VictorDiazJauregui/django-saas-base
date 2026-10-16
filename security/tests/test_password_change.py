from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from security.models import AuditLog
from security.redaction import REDACTED_PLACEHOLDER

from .account_links import with_account_links
from .api_test_case import CacheResetAPITestCase
from .test_throttling import override_rates
from .user_factory import DEFAULT_EMAIL, DEFAULT_PASSWORD, create_user

CHANGE_URL = "/api/v1/auth/password/change/"
LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/login/refresh/"
NEW_PASSWORD = "Changed-Passphrase-88"
PASSWORD_FIELDS = ("current_password", "new_password", "new_password2")


@with_account_links()
@override_rates(password=None)
class PasswordChangeTestCase(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}"
        )

    def change_password(self, **overrides):
        payload = {
            "current_password": DEFAULT_PASSWORD,
            "new_password": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
            **overrides,
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        return self.client.post(CHANGE_URL, payload, format="json")

    def log_in(self, password):
        payload = {"email": DEFAULT_EMAIL, "password": password}
        return self.client.post(LOGIN_URL, payload, format="json")

    def assert_rejected_on(self, response, field):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(field, response.data["fields"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(DEFAULT_PASSWORD))


class PasswordChangeTests(PasswordChangeTestCase):
    def test_changes_the_password_and_answers_204(self):
        response = self.change_password()

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.content, b"")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    def test_revokes_the_refresh_tokens_of_every_session(self):
        sessions = [str(RefreshToken.for_user(self.user)) for _ in range(2)]

        self.change_password()

        for refresh in sessions:
            response = self.client.post(
                REFRESH_URL, {"refresh": refresh}, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_only_the_new_password_logs_in(self):
        self.change_password()
        self.client.credentials()

        self.assertEqual(self.log_in(NEW_PASSWORD).status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.log_in(DEFAULT_PASSWORD).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_audit_stores_the_user_without_the_passwords(self):
        self.change_password()

        record = AuditLog.objects.get(path=CHANGE_URL)
        self.assertEqual(record.user, self.user)
        self.assertEqual(record.status_code, status.HTTP_204_NO_CONTENT)
        for field in PASSWORD_FIELDS:
            self.assertEqual(record.payload[field], REDACTED_PLACEHOLDER)


class PasswordChangeValidationTests(PasswordChangeTestCase):
    def test_wrong_current_password_is_rejected(self):
        response = self.change_password(current_password="Wrong-Passphrase-1")

        self.assert_rejected_on(response, "current_password")

    def test_weak_new_password_is_rejected(self):
        response = self.change_password(
            new_password="12345678", new_password2="12345678"
        )

        self.assert_rejected_on(response, "new_password")

    def test_new_password_similar_to_the_email_is_rejected(self):
        response = self.change_password(
            new_password=DEFAULT_EMAIL, new_password2=DEFAULT_EMAIL
        )

        self.assert_rejected_on(response, "new_password")

    def test_mismatched_confirmation_is_rejected(self):
        response = self.change_password(new_password2="Other-Passphrase-77")

        self.assert_rejected_on(response, "new_password2")

    def test_missing_field_is_rejected(self):
        for field in PASSWORD_FIELDS:
            with self.subTest(field=field):
                self.assert_rejected_on(self.change_password(**{field: None}), field)


class PasswordChangeAccessTests(PasswordChangeTestCase):
    def test_anonymous_request_is_unauthorized(self):
        self.client.credentials()

        response = self.change_password()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token_is_unauthorized(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")

        response = self.change_password()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_is_not_allowed(self):
        response = self.client.get(CHANGE_URL)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @override_rates(password="2/h")
    def test_the_password_scope_limits_the_attempts(self):
        statuses = [
            self.change_password(current_password="Wrong-Passphrase-1").status_code
            for _ in range(3)
        ]

        self.assertEqual(statuses[-1], status.HTTP_429_TOO_MANY_REQUESTS)

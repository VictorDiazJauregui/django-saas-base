from rest_framework import status

from security.models import AuditLog

from .api_test_case import CacheResetAPITestCase
from .user_factory import DEFAULT_EMAIL, DEFAULT_PASSWORD, create_user

LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/login/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
PROFILE_URL = "/api/v1/auth/me/"


class LogoutTestCase(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user()

    def obtain_tokens(self):
        payload = {"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD}
        return self.client.post(LOGIN_URL, payload, format="json").data

    def log_out(self, refresh_token):
        return self.client.post(LOGOUT_URL, {"refresh": refresh_token}, format="json")

    def last_logout_audit(self):
        return AuditLog.objects.filter(path=LOGOUT_URL).latest("timestamp")


class LogoutTests(LogoutTestCase):
    def test_logout_answers_an_empty_object(self):
        response = self.log_out(self.obtain_tokens()["refresh"])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {})

    def test_logged_out_refresh_token_stops_working(self):
        refresh_token = self.obtain_tokens()["refresh"]
        self.log_out(refresh_token)

        response = self.client.post(
            REFRESH_URL, {"refresh": refresh_token}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "token_not_valid")

    def test_access_token_keeps_working_until_it_expires(self):
        tokens = self.obtain_tokens()
        self.log_out(tokens["refresh"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        response = self.client.get(PROFILE_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_refresh_token_of_a_deleted_user_is_accepted(self):
        refresh_token = self.obtain_tokens()["refresh"]
        self.user.delete()

        response = self.log_out(refresh_token)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class LogoutErrorTests(LogoutTestCase):
    def test_logging_out_twice_is_unauthorized(self):
        refresh_token = self.obtain_tokens()["refresh"]
        self.log_out(refresh_token)

        response = self.log_out(refresh_token)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "token_not_valid")

    def test_malformed_token_is_unauthorized(self):
        response = self.log_out("not-a-token")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_token_is_not_a_refresh_token(self):
        response = self.log_out(self.obtain_tokens()["access"])

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_token_is_a_bad_request(self):
        response = self.client.post(LOGOUT_URL, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("refresh", response.data["fields"])

    def test_get_is_not_allowed(self):
        response = self.client.get(LOGOUT_URL)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class LogoutAuditTests(LogoutTestCase):
    def test_records_the_owner_of_the_refresh_token(self):
        self.log_out(self.obtain_tokens()["refresh"])

        audit = self.last_logout_audit()
        self.assertEqual(audit.user, self.user)
        self.assertEqual(audit.status_code, status.HTTP_200_OK)
        self.assertEqual(audit.payload, {"refresh": "[REDACTED]"})

    def test_failed_logout_records_no_user(self):
        self.log_out("not-a-token")

        audit = self.last_logout_audit()
        self.assertIsNone(audit.user)
        self.assertEqual(audit.status_code, status.HTTP_401_UNAUTHORIZED)

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.exceptions import api_exception_handler
from security.tests.api_test_case import CacheResetAPITestCase
from security.tests.test_throttling import override_rates
from security.tests.user_factory import DEFAULT_PASSWORD, create_user

REGISTER_URL = "/api/v1/auth/register/"
LOGIN_URL = "/api/v1/auth/login/"
ME_URL = "/api/v1/auth/me/"
ERROR_KEYS = {"code", "detail", "fields"}


def teapot_handler(exc, context):
    return Response({"replaced": True}, status=status.HTTP_418_IM_A_TEAPOT)


class ApiErrorShapeTests(CacheResetAPITestCase):
    def assertError(self, response, status_code, code):
        self.assertEqual(response.status_code, status_code)
        self.assertEqual(set(response.json()), ERROR_KEYS)
        self.assertEqual(response.json()["code"], code)
        self.assertIsInstance(response.json()["detail"], str)

    def test_validation_errors_go_under_fields(self):
        response = self.client.post(REGISTER_URL, {"email": "x"}, format="json")

        self.assertError(response, status.HTTP_400_BAD_REQUEST, "invalid")
        self.assertEqual(response.json()["detail"], "Invalid input.")
        self.assertEqual(
            response.json()["fields"]["email"], ["Enter a valid email address."]
        )

    def test_malformed_json_is_a_parse_error(self):
        response = self.client.post(
            REGISTER_URL, data='{"email": ', content_type="application/json"
        )

        self.assertError(response, status.HTTP_400_BAD_REQUEST, "parse_error")
        self.assertEqual(response.json()["fields"], {})

    def test_missing_token_is_not_authenticated(self):
        response = self.client.get(ME_URL)

        self.assertError(response, status.HTTP_401_UNAUTHORIZED, "not_authenticated")
        self.assertIn("WWW-Authenticate", response)

    def test_invalid_token_keeps_its_code_without_messages(self):
        response = self.client.get(ME_URL, HTTP_AUTHORIZATION="Bearer not-a-token")

        self.assertError(response, status.HTTP_401_UNAUTHORIZED, "token_not_valid")
        self.assertEqual(
            response.json()["detail"], "Given token not valid for any token type"
        )

    def test_failed_login_is_no_active_account(self):
        create_user()
        payload = {"email": "jane.doe@example.com", "password": "Wrong-Passphrase-1"}

        response = self.client.post(LOGIN_URL, payload, format="json")

        self.assertError(response, status.HTTP_401_UNAUTHORIZED, "no_active_account")

    @override_settings(ALLOW_PUBLIC_REGISTRATION=False)
    def test_permission_denied_keeps_its_message(self):
        response = self.client.post(REGISTER_URL, {}, format="json")

        self.assertError(response, status.HTTP_403_FORBIDDEN, "permission_denied")
        self.assertEqual(response.json()["detail"], "Public registration is disabled.")

    def test_method_not_allowed(self):
        self.client.force_authenticate(create_user())

        response = self.client.put(ME_URL, {}, format="json")

        self.assertError(
            response, status.HTTP_405_METHOD_NOT_ALLOWED, "method_not_allowed"
        )

    @override_rates(login="1/m")
    def test_throttled_keeps_retry_after(self):
        payload = {"email": "nobody@example.com", "password": DEFAULT_PASSWORD}
        self.client.post(LOGIN_URL, payload, format="json")

        response = self.client.post(LOGIN_URL, payload, format="json")

        self.assertError(response, status.HTTP_429_TOO_MANY_REQUESTS, "throttled")
        self.assertIn("Retry-After", response)

    @override_settings(
        REST_FRAMEWORK={
            **settings.REST_FRAMEWORK,
            "EXCEPTION_HANDLER": "core.tests.test_exceptions.teapot_handler",
        }
    )
    def test_a_project_can_replace_the_handler(self):
        response = self.client.get(ME_URL)

        self.assertEqual(response.status_code, status.HTTP_418_IM_A_TEAPOT)
        self.assertEqual(response.json(), {"replaced": True})


@override_settings(ROOT_URLCONF="core.tests.urls_failing_api_view")
class DjangoErrorPagesTests(CacheResetAPITestCase):
    def test_unknown_api_route_returns_json(self):
        response = self.client.get("/api/v1/nothing/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.json(), {"code": "not_found", "detail": "Not found.", "fields": {}}
        )

    def test_unknown_route_outside_the_api_keeps_the_html_page(self):
        response = self.client.get("/nothing/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(response["Content-Type"].startswith("text/html"))

    def test_unhandled_error_in_the_api_returns_json(self):
        self.client.raise_request_exception = False

        # assertLogs also keeps the expected traceback out of the test output.
        with self.assertLogs("django.request", "ERROR"):
            response = self.client.get("/api/v1/failing/")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(
            response.json(),
            {
                "code": "server_error",
                "detail": "A server error occurred.",
                "fields": {},
            },
        )

    def test_unhandled_error_outside_the_api_keeps_the_html_page(self):
        self.client.raise_request_exception = False

        with self.assertLogs("django.request", "ERROR"):
            response = self.client.get("/failing/")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertTrue(response["Content-Type"].startswith("text/html"))


class ValidationErrorFieldsTests(SimpleTestCase):
    def handle(self, detail):
        return api_exception_handler(ValidationError(detail), {}).data

    def test_a_message_without_field_goes_to_non_field_errors(self):
        body = self.handle("Passwords don't match.")

        self.assertEqual(
            body["fields"], {"non_field_errors": ["Passwords don't match."]}
        )

    def test_nested_errors_are_kept(self):
        body = self.handle({"address": {"city": ["This field is required."]}})

        self.assertEqual(
            body["fields"], {"address": {"city": ["This field is required."]}}
        )

    def test_unhandled_exceptions_are_left_to_django(self):
        self.assertIsNone(api_exception_handler(KeyError("boom"), {}))

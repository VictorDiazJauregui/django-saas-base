from django.test import override_settings
from rest_framework import status

from security.tests.api_test_case import CacheResetAPITestCase

FRONTEND_ORIGIN = "http://localhost:5173"
OTHER_ORIGIN = "https://evil.example"
LOGIN_URL = "/api/v1/auth/login/"
ALLOW_ORIGIN = "Access-Control-Allow-Origin"


@override_settings(CORS_ALLOWED_ORIGINS=[FRONTEND_ORIGIN])
class CorsTests(CacheResetAPITestCase):
    def preflight(self, path, origin):
        return self.client.options(
            path,
            HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type",
        )

    def test_preflight_from_an_allowed_origin_gets_the_headers(self):
        response = self.preflight(LOGIN_URL, FRONTEND_ORIGIN)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response[ALLOW_ORIGIN], FRONTEND_ORIGIN)
        self.assertIn("POST", response["Access-Control-Allow-Methods"])
        self.assertIn("authorization", response["Access-Control-Allow-Headers"])

    def test_preflight_from_another_origin_gets_no_headers(self):
        response = self.preflight(LOGIN_URL, OTHER_ORIGIN)

        self.assertNotIn(ALLOW_ORIGIN, response)

    def test_actual_request_from_an_allowed_origin_gets_the_headers(self):
        response = self.client.post(
            LOGIN_URL, {}, format="json", HTTP_ORIGIN=FRONTEND_ORIGIN
        )

        self.assertEqual(response[ALLOW_ORIGIN], FRONTEND_ORIGIN)
        self.assertEqual(response["Access-Control-Expose-Headers"], "Retry-After")

    def test_credentials_are_never_allowed(self):
        response = self.preflight(LOGIN_URL, FRONTEND_ORIGIN)

        self.assertNotIn("Access-Control-Allow-Credentials", response)

    def test_admin_is_not_exposed_to_other_origins(self):
        response = self.preflight("/admin/login/", FRONTEND_ORIGIN)

        self.assertNotIn(ALLOW_ORIGIN, response)

    @override_settings(CORS_ALLOWED_ORIGINS=[])
    def test_an_empty_list_allows_no_origin(self):
        response = self.preflight(LOGIN_URL, FRONTEND_ORIGIN)

        self.assertNotIn(ALLOW_ORIGIN, response)

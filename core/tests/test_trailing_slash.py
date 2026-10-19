from django.test import override_settings
from rest_framework import status

from security.tests.api_test_case import LanguageResetAPITestCase

LOGIN_PATH = "/api/v1/auth/login"
HEALTH_PATH = "/api/v1/health"
ME_PATH = "/api/v1/auth/me"


class ApiTrailingSlashTests(LanguageResetAPITestCase):
    def assertTrailingSlashError(self, response, expected_path):
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.json(),
            {
                "code": "trailing_slash_required",
                "detail": f"This route ends with a slash: use {expected_path}.",
                "fields": {},
            },
        )

    def test_post_without_slash_returns_json_instead_of_redirecting(self):
        response = self.client.post(LOGIN_PATH, {"email": "x"}, format="json")

        self.assertTrailingSlashError(response, f"{LOGIN_PATH}/")

    @override_settings(DEBUG=True)
    def test_post_without_slash_returns_json_with_debug(self):
        response = self.client.post(LOGIN_PATH, {"email": "x"}, format="json")

        self.assertTrailingSlashError(response, f"{LOGIN_PATH}/")

    def test_get_without_slash_returns_json(self):
        response = self.client.get(HEALTH_PATH)

        self.assertTrailingSlashError(response, f"{HEALTH_PATH}/")

    def test_patch_without_slash_returns_json(self):
        response = self.client.patch(ME_PATH, {"first_name": "Ada"}, format="json")

        self.assertTrailingSlashError(response, f"{ME_PATH}/")

    def test_detail_keeps_the_query_string(self):
        response = self.client.get(HEALTH_PATH, {"verbose": "1"})

        self.assertTrailingSlashError(response, f"{HEALTH_PATH}/?verbose=1")

    def test_detail_follows_the_request_language(self):
        response = self.client.get(HEALTH_PATH, HTTP_ACCEPT_LANGUAGE="es")

        self.assertEqual(
            response.json()["detail"],
            f"Esta ruta termina en barra: usa {HEALTH_PATH}/.",
        )

    def test_route_with_slash_is_unchanged(self):
        response = self.client.get(f"{HEALTH_PATH}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unknown_route_is_still_not_found(self):
        response = self.client.get("/api/v1/nothing")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["code"], "not_found")

    def test_admin_keeps_the_redirect(self):
        response = self.client.get("/admin")

        self.assertEqual(response.status_code, status.HTTP_301_MOVED_PERMANENTLY)
        self.assertEqual(response["Location"], "/admin/")

    @override_settings(APPEND_SLASH=False)
    def test_without_append_slash_it_is_a_plain_not_found(self):
        response = self.client.get(HEALTH_PATH)

        self.assertEqual(response.json()["code"], "not_found")

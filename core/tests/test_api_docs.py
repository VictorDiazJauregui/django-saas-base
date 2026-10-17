from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

SCHEMA_URL = "/api/schema/"
DOCS_URL = "/api/docs/"
DOCS_URLS = (SCHEMA_URL, DOCS_URL)
PASSWORD = "Str0ng-Passphrase-42"


def create_account(email, **extra):
    return get_user_model().objects.create_user(email=email, password=PASSWORD, **extra)


@override_settings(API_DOCS_ENABLED=True)
class EnabledApiDocsTests(APITestCase):
    def test_schema_is_served_as_yaml(self):
        response = self.client.get(SCHEMA_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("openapi", response["Content-Type"])
        self.assertTrue(response.content.startswith(b"openapi: 3.0.3"))

    def test_schema_is_served_as_json_on_request(self):
        response = self.client.get(SCHEMA_URL, {"format": "json"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["openapi"], "3.0.3")

    def test_swagger_ui_loads_its_assets_from_the_backend(self):
        response = self.client.get(DOCS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        page = response.content.decode()
        self.assertIn("swagger-ui", page)
        self.assertIn("/static/drf_spectacular_sidecar/swagger-ui-dist/", page)
        self.assertNotIn("cdn.jsdelivr.net", page)

    def test_schema_only_answers_get(self):
        response = self.client.post(SCHEMA_URL, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(response.json()["code"], "method_not_allowed")


@override_settings(API_DOCS_ENABLED=False)
class DisabledApiDocsTests(APITestCase):
    def assertHidden(self):
        missing_route = self.client.get("/api/v1/missing/").json()
        for url in DOCS_URLS:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
                self.assertEqual(response.json(), missing_route)

    def assertVisible(self):
        for url in DOCS_URLS:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def authenticate_with_token(self, user):
        access = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_anonymous_gets_the_same_404_as_a_missing_route(self):
        self.assertHidden()

    def test_user_without_staff_status_gets_404(self):
        self.authenticate_with_token(create_account("jane@example.com"))

        self.assertHidden()

    def test_staff_with_a_token_sees_the_docs(self):
        self.authenticate_with_token(create_account("staff@example.com", is_staff=True))

        self.assertVisible()

    def test_staff_logged_in_to_the_admin_sees_the_docs(self):
        self.client.force_login(create_account("staff@example.com", is_staff=True))

        self.assertVisible()

    def test_inactive_staff_session_gets_404(self):
        staff = create_account("staff@example.com", is_staff=True, is_active=False)
        self.client.force_login(staff)

        self.assertHidden()

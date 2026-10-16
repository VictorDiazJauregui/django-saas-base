from unittest import mock

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView

from core.tests.settings_subprocess import read_settings
from security.tests.api_test_case import CacheResetAPITestCase
from security.tests.user_factory import create_user

ME_URL = "/api/v1/auth/me/"
JSON_RENDERER = "rest_framework.renderers.JSONRenderer"
BROWSABLE_RENDERER = "rest_framework.renderers.BrowsableAPIRenderer"
BROWSER_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"


def renderer_classes(**overrides):
    values = read_settings(["REST_FRAMEWORK"], **overrides)
    return values["REST_FRAMEWORK"]["DEFAULT_RENDERER_CLASSES"]


class RendererSettingsTests(SimpleTestCase):
    def test_only_json_without_debug(self):
        for environment in ("prod", "staging", "local"):
            with self.subTest(environment=environment):
                classes = renderer_classes(ENVIRONMENT=environment, DEBUG="False")

                self.assertEqual(classes, [JSON_RENDERER])

    def test_browsable_api_stays_in_development(self):
        classes = renderer_classes(ENVIRONMENT="local", DEBUG="True")

        self.assertEqual(classes, [JSON_RENDERER, BROWSABLE_RENDERER])


class JsonOnlyResponseTests(CacheResetAPITestCase):
    # DRF copies DEFAULT_RENDERER_CLASSES into APIView when it is imported, so
    # override_settings can't change them: the views get the production list directly.
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(APIView, "renderer_classes", [JSONRenderer])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client.force_authenticate(create_user())

    def test_a_browser_gets_json(self):
        response = self.client.get(ME_URL, HTTP_ACCEPT=BROWSER_ACCEPT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_asking_only_for_html_is_not_acceptable(self):
        response = self.client.get(ME_URL, HTTP_ACCEPT="text/html")

        self.assertEqual(response.status_code, status.HTTP_406_NOT_ACCEPTABLE)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json()["code"], "not_acceptable")

    def test_the_browsable_api_format_is_not_served(self):
        response = self.client.get(f"{ME_URL}?format=api")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response["Content-Type"], "application/json")

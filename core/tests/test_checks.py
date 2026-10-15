import os
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.checks import Error, Warning
from django.test import SimpleTestCase, override_settings

from core.checks import (
    EXAMPLE_ADMIN_PASSWORD,
    EXAMPLE_DB_PASSWORD,
    EXAMPLE_SECRET_KEY,
    check_example_values,
)

ENV_EXAMPLE = Path(settings.BASE_DIR) / ".env.example"
VALID_SECRET_KEY = "a-valid-secret-key-that-is-not-the-example-0123456789"
VALID_PASSWORD = "not-the-example-password"


def read_env_example_value(name):
    for line in ENV_EXAMPLE.read_text().splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1]
    raise AssertionError(f"{name} is missing from .env.example")


def patch_db_password(password):
    return mock.patch.dict(settings.DATABASES["default"], {"PASSWORD": password})


def patch_admin_password(password):
    return mock.patch.dict(os.environ, {"ADMIN_PASSWORD": password})


@override_settings(SECRET_KEY=VALID_SECRET_KEY, ENVIRONMENT="local")
class ExampleValueCheckTests(SimpleTestCase):
    def setUp(self):
        for patcher in (
            patch_db_password(VALID_PASSWORD),
            patch_admin_password(VALID_PASSWORD),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def check_ids(self):
        return [message.id for message in check_example_values(None)]

    def test_valid_values_raise_nothing(self):
        self.assertEqual(self.check_ids(), [])

    def test_example_secret_key_is_reported(self):
        with self.settings(SECRET_KEY=EXAMPLE_SECRET_KEY):
            self.assertEqual(self.check_ids(), ["core.W001"])

    def test_example_db_password_is_reported(self):
        with patch_db_password(EXAMPLE_DB_PASSWORD):
            self.assertEqual(self.check_ids(), ["core.W002"])

    def test_example_admin_password_is_reported(self):
        with patch_admin_password(EXAMPLE_ADMIN_PASSWORD):
            self.assertEqual(self.check_ids(), ["core.W003"])

    def test_missing_admin_password_is_not_reported(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("ADMIN_PASSWORD")
            self.assertEqual(self.check_ids(), [])

    def test_example_values_are_warnings_in_development(self):
        with self.settings(SECRET_KEY=EXAMPLE_SECRET_KEY, ENVIRONMENT="ci"):
            messages = check_example_values(None)

        self.assertIsInstance(messages[0], Warning)
        self.assertNotIsInstance(messages[0], Error)

    def test_example_values_are_errors_when_deployed(self):
        for environment in ("staging", "prod"):
            with self.subTest(environment=environment):
                with self.settings(
                    SECRET_KEY=EXAMPLE_SECRET_KEY, ENVIRONMENT=environment
                ):
                    messages = check_example_values(None)

                self.assertIsInstance(messages[0], Error)
                self.assertEqual(messages[0].id, "core.E001")


class ExampleConstantsTests(SimpleTestCase):
    def test_constants_match_env_example(self):
        expected = {
            "SECRET_KEY": EXAMPLE_SECRET_KEY,
            "DB_PASSWORD": EXAMPLE_DB_PASSWORD,
            "ADMIN_PASSWORD": EXAMPLE_ADMIN_PASSWORD,
        }

        for name, constant in expected.items():
            with self.subTest(name=name):
                self.assertEqual(read_env_example_value(name), constant)

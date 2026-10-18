from django.test import SimpleTestCase

from .settings_subprocess import read_settings, run_manage_command

MANIFEST_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
PLAIN_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"


def database_option(name, **overrides):
    return read_settings(["DATABASES"], **overrides)["DATABASES"]["default"][name]


class ConnectionReuseSettingsTests(SimpleTestCase):
    def test_keeps_connections_for_a_minute_by_default(self):
        self.assertEqual(database_option("CONN_MAX_AGE"), 60)

    def test_reads_the_lifetime_from_the_environment(self):
        for raw, expected in (("0", 0), ("300", 300)):
            with self.subTest(raw=raw):
                self.assertEqual(
                    database_option("CONN_MAX_AGE", DB_CONN_MAX_AGE=raw), expected
                )

    def test_checks_a_reused_connection_before_using_it(self):
        self.assertTrue(database_option("CONN_HEALTH_CHECKS"))

    def test_invalid_lifetime_fails_to_start(self):
        for raw in ("-1", "abc"):
            with self.subTest(raw=raw):
                result = run_manage_command(["check"], DB_CONN_MAX_AGE=raw)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("DB_CONN_MAX_AGE", result.stderr)


class LoggingSettingsTests(SimpleTestCase):
    def test_text_at_info_by_default(self):
        logging_config = read_settings(["LOGGING"])["LOGGING"]

        self.assertEqual(logging_config["root"]["level"], "INFO")
        self.assertEqual(logging_config["handlers"]["console"]["formatter"], "text")

    def test_json_format_from_the_environment(self):
        logging_config = read_settings(
            ["LOGGING"], LOG_FORMAT="json", LOG_LEVEL="warning"
        )["LOGGING"]

        self.assertEqual(logging_config["root"]["level"], "WARNING")
        self.assertEqual(logging_config["handlers"]["console"]["formatter"], "json")

    def test_invalid_values_fail_to_start(self):
        for name, raw in (("LOG_LEVEL", "verbose"), ("LOG_FORMAT", "xml")):
            with self.subTest(name=name):
                result = run_manage_command(["check"], **{name: raw})

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"{name}={raw!r}", result.stderr)


class StaticFilesSettingsTests(SimpleTestCase):
    def test_deployed_environments_serve_hashed_compressed_files(self):
        for environment in ("staging", "prod"):
            with self.subTest(environment=environment):
                storages = read_settings(["STORAGES"], ENVIRONMENT=environment)[
                    "STORAGES"
                ]

                self.assertEqual(storages["staticfiles"]["BACKEND"], MANIFEST_STORAGE)

    # The manifest only exists after collectstatic, which local work and the tests never run.
    def test_local_and_ci_keep_the_plain_storage(self):
        for environment in ("local", "ci"):
            with self.subTest(environment=environment):
                storages = read_settings(
                    ["STORAGES"], ENVIRONMENT=environment, ALLOWED_HOSTS=""
                )["STORAGES"]

                self.assertEqual(storages["staticfiles"]["BACKEND"], PLAIN_STORAGE)

    def test_whitenoise_only_refreshes_outside_deployed_environments(self):
        cases = (
            ({"ENVIRONMENT": "prod"}, False),
            ({"ENVIRONMENT": "staging"}, False),
            ({"ENVIRONMENT": "ci", "ALLOWED_HOSTS": ""}, True),
        )
        for overrides, expected in cases:
            with self.subTest(environment=overrides["ENVIRONMENT"]):
                values = read_settings(["WHITENOISE_AUTOREFRESH"], **overrides)

                self.assertEqual(values["WHITENOISE_AUTOREFRESH"], expected)

    def test_whitenoise_comes_right_after_the_security_middleware(self):
        middleware = read_settings(["MIDDLEWARE"])["MIDDLEWARE"]

        self.assertEqual(
            middleware[:2],
            [
                "django.middleware.security.SecurityMiddleware",
                "whitenoise.middleware.WhiteNoiseMiddleware",
            ],
        )

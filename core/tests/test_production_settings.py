from django.test import SimpleTestCase

from .settings_subprocess import read_settings, run_manage_command


class EnvironmentStartupTests(SimpleTestCase):
    def test_unknown_environment_fails_to_start(self):
        result = run_manage_command(["check"], ENVIRONMENT="production")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ImproperlyConfigured", result.stderr)
        self.assertIn("ENVIRONMENT='production'", result.stderr)

    def test_debug_in_deployed_environments_fails_to_start(self):
        for environment in ("staging", "prod"):
            with self.subTest(environment=environment):
                result = run_manage_command(
                    ["check"], ENVIRONMENT=environment, DEBUG="True"
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("DEBUG=True", result.stderr)

    def test_debug_is_allowed_locally(self):
        values = read_settings(["DEBUG"], ENVIRONMENT="local", DEBUG="True")

        self.assertTrue(values["DEBUG"])


class AllowedHostsStartupTests(SimpleTestCase):
    def test_wildcard_hosts_fail_in_production(self):
        result = run_manage_command(["check"], ALLOWED_HOSTS="*")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ALLOWED_HOSTS", result.stderr)

    def test_empty_hosts_fail_in_production(self):
        result = run_manage_command(["check"], ALLOWED_HOSTS="")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ALLOWED_HOSTS", result.stderr)

    def test_explicit_domain_starts_in_production(self):
        values = read_settings(["ALLOWED_HOSTS"], ALLOWED_HOSTS="api.example.com")

        self.assertEqual(values["ALLOWED_HOSTS"], ["api.example.com"])

    def test_match_all_csrf_origin_fails_in_production(self):
        result = run_manage_command(["check"], CSRF_TRUSTED_ORIGINS="https://*")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CSRF_TRUSTED_ORIGINS", result.stderr)


class ProductionSecurityTests(SimpleTestCase):
    def test_deploy_check_passes_without_warnings(self):
        result = run_manage_command(["check", "--deploy", "--fail-level", "WARNING"])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no issues", result.stdout)

    def test_production_forces_https_and_secure_cookies(self):
        names = [
            "SECURE_SSL_REDIRECT",
            "SESSION_COOKIE_SECURE",
            "CSRF_COOKIE_SECURE",
            "SECURE_HSTS_SECONDS",
        ]

        values = read_settings(names)

        self.assertEqual(
            values,
            {
                "SECURE_SSL_REDIRECT": True,
                "SESSION_COOKIE_SECURE": True,
                "CSRF_COOKIE_SECURE": True,
                "SECURE_HSTS_SECONDS": 3600,
            },
        )

    def test_hsts_options_come_from_the_environment(self):
        names = ["SECURE_HSTS_INCLUDE_SUBDOMAINS", "SECURE_HSTS_PRELOAD"]

        values = read_settings(
            names, SECURE_HSTS_INCLUDE_SUBDOMAINS="True", SECURE_HSTS_PRELOAD="True"
        )

        self.assertEqual(values, dict.fromkeys(names, True))

    def test_local_keeps_plain_http(self):
        values = read_settings(["SECURE_SSL_REDIRECT"], ENVIRONMENT="local")

        self.assertFalse(values["SECURE_SSL_REDIRECT"])

    def test_forwarded_proto_header_is_trusted_only_when_enabled(self):
        enabled = read_settings(
            ["SECURE_PROXY_SSL_HEADER"], USE_X_FORWARDED_PROTO="True"
        )
        disabled = read_settings(["SECURE_PROXY_SSL_HEADER"])

        self.assertEqual(
            enabled["SECURE_PROXY_SSL_HEADER"], ["HTTP_X_FORWARDED_PROTO", "https"]
        )
        self.assertIsNone(disabled["SECURE_PROXY_SSL_HEADER"])

    def test_csrf_trusted_origins_are_read_as_a_list(self):
        values = read_settings(
            ["CSRF_TRUSTED_ORIGINS"],
            CSRF_TRUSTED_ORIGINS="https://admin.example.com,https://app.example.com",
        )

        self.assertEqual(
            values["CSRF_TRUSTED_ORIGINS"],
            ["https://admin.example.com", "https://app.example.com"],
        )

    def test_short_secret_key_is_reported_by_django(self):
        result = run_manage_command(["check", "--deploy"], SECRET_KEY="short-key")

        self.assertIn("security.W009", result.stderr)


class ThrottleRateStartupTests(SimpleTestCase):
    def test_invalid_rate_fails_to_start(self):
        result = run_manage_command(["check"], THROTTLE_LOGIN_RATE="10/x")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("'10/x'", result.stderr)

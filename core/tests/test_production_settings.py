from django.test import SimpleTestCase

from .settings_subprocess import STRONG_SECRET_KEY, read_settings, run_manage_command


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


class TrustedProxyCountStartupTests(SimpleTestCase):
    def test_negative_count_fails_to_start(self):
        result = run_manage_command(["check"], TRUSTED_PROXY_COUNT="-1")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TRUSTED_PROXY_COUNT=-1", result.stderr)

    def test_count_feeds_the_audit_and_the_throttling(self):
        values = read_settings(
            ["TRUSTED_PROXY_COUNT", "REST_FRAMEWORK"], TRUSTED_PROXY_COUNT="2"
        )

        self.assertEqual(values["TRUSTED_PROXY_COUNT"], 2)
        self.assertEqual(values["REST_FRAMEWORK"]["NUM_PROXIES"], 2)


class AuditExtraSensitiveKeysStartupTests(SimpleTestCase):
    def test_extra_keys_are_read_as_a_list(self):
        values = read_settings(
            ["AUDIT_EXTRA_SENSITIVE_KEYS"], AUDIT_EXTRA_SENSITIVE_KEYS="tax-id,iban"
        )

        self.assertEqual(values["AUDIT_EXTRA_SENSITIVE_KEYS"], ["tax-id", "iban"])


class TokenLifetimeStartupTests(SimpleTestCase):
    def test_lifetimes_come_from_the_environment(self):
        values = read_settings(
            ["SIMPLE_JWT"], JWT_ACCESS_MINUTES="10", JWT_REFRESH_DAYS="7"
        )

        self.assertEqual(values["SIMPLE_JWT"]["ACCESS_TOKEN_LIFETIME"], "0:10:00")
        self.assertEqual(
            values["SIMPLE_JWT"]["REFRESH_TOKEN_LIFETIME"], "7 days, 0:00:00"
        )

    def test_refresh_tokens_rotate_into_the_blacklist(self):
        jwt_settings = read_settings(["SIMPLE_JWT"])["SIMPLE_JWT"]

        self.assertTrue(jwt_settings["ROTATE_REFRESH_TOKENS"])
        self.assertTrue(jwt_settings["BLACKLIST_AFTER_ROTATION"])

    def test_empty_signing_key_falls_back_to_the_secret_key(self):
        jwt_settings = read_settings(["SIMPLE_JWT"], JWT_SIGNING_KEY="")["SIMPLE_JWT"]

        self.assertEqual(jwt_settings["SIGNING_KEY"], STRONG_SECRET_KEY)

    def test_own_signing_key_is_used_when_set(self):
        own_key = "own-signing-key-for-the-tokens-0123456789"
        jwt_settings = read_settings(["SIMPLE_JWT"], JWT_SIGNING_KEY=own_key)[
            "SIMPLE_JWT"
        ]

        self.assertEqual(jwt_settings["SIGNING_KEY"], own_key)

    def test_invalid_lifetimes_fail_to_start(self):
        for variable, value in (
            ("JWT_ACCESS_MINUTES", "0"),
            ("JWT_REFRESH_DAYS", "-1"),
        ):
            with self.subTest(variable=variable):
                result = run_manage_command(["check"], **{variable: value})

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(variable, result.stderr)


class LoginLockoutStartupTests(SimpleTestCase):
    def test_lockout_settings_come_from_the_environment(self):
        names = ["AXES_FAILURE_LIMIT", "AXES_COOLOFF_TIME", "AXES_LOCKOUT_PARAMETERS"]

        values = read_settings(
            names,
            AXES_FAILURE_LIMIT="3",
            AXES_COOLOFF_MINUTES="30",
            AXES_LOCKOUT_PARAMETERS="username+ip_address,user_agent",
        )

        self.assertEqual(values["AXES_FAILURE_LIMIT"], 3)
        self.assertEqual(values["AXES_COOLOFF_TIME"], "0:30:00")
        self.assertEqual(
            values["AXES_LOCKOUT_PARAMETERS"],
            [["username", "ip_address"], "user_agent"],
        )

    def test_invalid_lockout_settings_fail_to_start(self):
        cases = (
            ("AXES_FAILURE_LIMIT", "0"),
            ("AXES_COOLOFF_MINUTES", "abc"),
            ("AXES_LOCKOUT_PARAMETERS", "username+email"),
        )
        for variable, value in cases:
            with self.subTest(variable=variable):
                result = run_manage_command(["check"], **{variable: value})

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(variable, result.stderr)


class AuditPayloadLimitStartupTests(SimpleTestCase):
    def test_limit_is_read_as_a_number(self):
        values = read_settings(["AUDIT_PAYLOAD_MAX_BYTES"], AUDIT_PAYLOAD_MAX_BYTES="0")

        self.assertEqual(values["AUDIT_PAYLOAD_MAX_BYTES"], 0)

    def test_invalid_limit_fails_to_start(self):
        for value in ("-1", "abc"):
            with self.subTest(value=value):
                result = run_manage_command(["check"], AUDIT_PAYLOAD_MAX_BYTES=value)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("AUDIT_PAYLOAD_MAX_BYTES", result.stderr)


class CorsStartupTests(SimpleTestCase):
    def test_no_origin_is_allowed_by_default(self):
        values = read_settings(["CORS_ALLOWED_ORIGINS"])

        self.assertEqual(values["CORS_ALLOWED_ORIGINS"], [])

    def test_origins_are_read_as_a_list(self):
        values = read_settings(
            ["CORS_ALLOWED_ORIGINS"],
            CORS_ALLOWED_ORIGINS="https://app.example.com,http://localhost:5173",
        )

        self.assertEqual(
            values["CORS_ALLOWED_ORIGINS"],
            ["https://app.example.com", "http://localhost:5173"],
        )

    def test_an_origin_without_scheme_fails_to_start(self):
        for origin in ("*", "app.example.com"):
            with self.subTest(origin=origin):
                result = run_manage_command(["check"], CORS_ALLOWED_ORIGINS=origin)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("corsheaders.E013", result.stderr)


class PaginationStartupTests(SimpleTestCase):
    def test_page_sizes_are_read_as_numbers(self):
        values = read_settings(
            ["API_PAGE_SIZE", "API_MAX_PAGE_SIZE"],
            API_PAGE_SIZE="50",
            API_MAX_PAGE_SIZE="500",
        )

        self.assertEqual(values["API_PAGE_SIZE"], 50)
        self.assertEqual(values["API_MAX_PAGE_SIZE"], 500)

    def test_invalid_page_sizes_fail_to_start(self):
        cases = (
            ("API_PAGE_SIZE", "0"),
            ("API_PAGE_SIZE", "abc"),
            ("API_MAX_PAGE_SIZE", "-1"),
        )
        for variable, value in cases:
            with self.subTest(variable=variable, value=value):
                result = run_manage_command(["check"], **{variable: value})

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(variable, result.stderr)

    def test_page_size_above_the_maximum_fails_to_start(self):
        result = run_manage_command(
            ["check"], API_PAGE_SIZE="200", API_MAX_PAGE_SIZE="100"
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("API_PAGE_SIZE=200", result.stderr)
        self.assertIn("API_MAX_PAGE_SIZE=100", result.stderr)

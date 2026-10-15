from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from core.environment import (
    default_allowed_hosts,
    is_deployed,
    silenced_hsts_checks,
    validate_allowed_hosts,
    validate_csrf_trusted_origins,
    validate_debug,
    validate_environment,
    validate_trusted_proxy_count,
)


class ValidateEnvironmentTests(SimpleTestCase):
    def test_accepts_the_four_known_environments(self):
        for name in ("local", "ci", "staging", "prod"):
            with self.subTest(name=name):
                self.assertEqual(validate_environment(name), name)

    def test_rejects_unknown_names_listing_the_valid_ones(self):
        for name in ("production", "PROD", "dev", ""):
            with self.subTest(name=name):
                with self.assertRaisesMessage(
                    ImproperlyConfigured, "local, ci, staging, prod"
                ):
                    validate_environment(name)

    def test_only_staging_and_prod_are_deployed(self):
        self.assertTrue(is_deployed("staging"))
        self.assertTrue(is_deployed("prod"))
        self.assertFalse(is_deployed("local"))
        self.assertFalse(is_deployed("ci"))


class ValidateDebugTests(SimpleTestCase):
    def test_allows_debug_in_development_environments(self):
        self.assertTrue(validate_debug(True, "local"))
        self.assertTrue(validate_debug(True, "ci"))

    def test_rejects_debug_in_deployed_environments(self):
        for name in ("staging", "prod"):
            with self.subTest(name=name):
                with self.assertRaisesMessage(ImproperlyConfigured, "DEBUG=True"):
                    validate_debug(True, name)

    def test_allows_debug_off_everywhere(self):
        self.assertFalse(validate_debug(False, "prod"))


class AllowedHostsTests(SimpleTestCase):
    def test_development_keeps_the_permissive_defaults(self):
        self.assertEqual(default_allowed_hosts("local", debug=True), ["*"])
        self.assertEqual(default_allowed_hosts("ci", debug=False), ["localhost"])

    def test_deployed_environments_have_no_default(self):
        self.assertEqual(default_allowed_hosts("prod", debug=False), [])

    def test_rejects_empty_or_wildcard_hosts_when_deployed(self):
        for hosts in ([], ["*"], ["api.example.com", "*"]):
            with self.subTest(hosts=hosts):
                with self.assertRaisesMessage(ImproperlyConfigured, "ALLOWED_HOSTS"):
                    validate_allowed_hosts(hosts, "prod")

    def test_accepts_explicit_domains_when_deployed(self):
        hosts = ["api.example.com", ".example.org"]

        self.assertEqual(validate_allowed_hosts(hosts, "staging"), hosts)

    def test_development_accepts_the_wildcard(self):
        self.assertEqual(validate_allowed_hosts(["*"], "local"), ["*"])


class CsrfTrustedOriginsTests(SimpleTestCase):
    def test_empty_is_valid_everywhere(self):
        self.assertEqual(validate_csrf_trusted_origins([], "prod"), [])

    def test_rejects_a_match_all_origin_when_deployed(self):
        for origin in ("*", "https://*", "http://*"):
            with self.subTest(origin=origin):
                with self.assertRaisesMessage(
                    ImproperlyConfigured, "CSRF_TRUSTED_ORIGINS"
                ):
                    validate_csrf_trusted_origins([origin], "prod")

    def test_accepts_subdomain_wildcards_and_explicit_origins(self):
        origins = ["https://admin.example.com", "https://*.example.com"]

        self.assertEqual(validate_csrf_trusted_origins(origins, "prod"), origins)

    def test_development_accepts_anything(self):
        self.assertEqual(validate_csrf_trusted_origins(["*"], "local"), ["*"])


class SilencedHstsChecksTests(SimpleTestCase):
    def test_silences_the_warnings_of_the_options_left_off(self):
        self.assertEqual(
            silenced_hsts_checks(include_subdomains=False, preload=False),
            ["security.W005", "security.W021"],
        )

    def test_silences_nothing_once_the_options_are_on(self):
        self.assertEqual(
            silenced_hsts_checks(include_subdomains=True, preload=True), []
        )


class TrustedProxyCountTests(SimpleTestCase):
    def test_accepts_zero_and_positive_counts(self):
        for count in (0, 1, 3):
            with self.subTest(count=count):
                self.assertEqual(validate_trusted_proxy_count(count), count)

    def test_rejects_negative_counts(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "TRUSTED_PROXY_COUNT=-1"):
            validate_trusted_proxy_count(-1)

from django.test import SimpleTestCase

from .settings_subprocess import read_settings, run_manage_command

RESET_URL = "https://app.example.com/reset-password?uid={uid}&token={token}"
VERIFICATION_URL = "https://app.example.com/verify-email?uid={uid}&token={token}"


class PasswordResetSettingsTests(SimpleTestCase):
    def assert_fails_to_start(self, expected_text, **overrides):
        result = run_manage_command(["check"], **overrides)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(expected_text, result.stderr)

    def test_reset_url_comes_from_the_environment(self):
        values = read_settings(["FRONTEND_PASSWORD_RESET_URL"])

        self.assertEqual(values["FRONTEND_PASSWORD_RESET_URL"], RESET_URL)

    def test_reset_url_without_a_marker_fails_to_start(self):
        for url in (
            "https://app.example.com/reset?uid={uid}",
            "https://app.example.com/reset?token={token}",
        ):
            with self.subTest(url=url):
                self.assert_fails_to_start(
                    "FRONTEND_PASSWORD_RESET_URL", FRONTEND_PASSWORD_RESET_URL=url
                )

    def test_reset_url_without_scheme_or_host_fails_to_start(self):
        for url in (
            "app.example.com/r?uid={uid}&token={token}",
            "https://?uid={uid}&token={token}",
        ):
            with self.subTest(url=url):
                self.assert_fails_to_start(
                    "FRONTEND_PASSWORD_RESET_URL", FRONTEND_PASSWORD_RESET_URL=url
                )

    def test_missing_reset_url_fails_to_start(self):
        self.assert_fails_to_start(
            "FRONTEND_PASSWORD_RESET_URL", FRONTEND_PASSWORD_RESET_URL=""
        )

    def test_reset_timeout_is_read_in_minutes(self):
        values = read_settings(
            ["PASSWORD_RESET_TIMEOUT"], PASSWORD_RESET_TIMEOUT_MINUTES="30"
        )

        self.assertEqual(values["PASSWORD_RESET_TIMEOUT"], 1800)

    def test_invalid_reset_timeout_fails_to_start(self):
        self.assert_fails_to_start(
            "PASSWORD_RESET_TIMEOUT_MINUTES", PASSWORD_RESET_TIMEOUT_MINUTES="0"
        )


class EmailVerificationSettingsTests(SimpleTestCase):
    def test_verification_is_off_by_default(self):
        values = read_settings(["REQUIRE_EMAIL_VERIFICATION"])

        self.assertFalse(values["REQUIRE_EMAIL_VERIFICATION"])

    def test_verification_needs_its_frontend_url(self):
        result = run_manage_command(
            ["check"],
            REQUIRE_EMAIL_VERIFICATION="True",
            FRONTEND_EMAIL_VERIFICATION_URL="",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FRONTEND_EMAIL_VERIFICATION_URL", result.stderr)

    def test_verification_settings_come_from_the_environment(self):
        names = [
            "REQUIRE_EMAIL_VERIFICATION",
            "FRONTEND_EMAIL_VERIFICATION_URL",
            "EMAIL_VERIFICATION_TIMEOUT",
        ]

        values = read_settings(
            names,
            REQUIRE_EMAIL_VERIFICATION="True",
            FRONTEND_EMAIL_VERIFICATION_URL=VERIFICATION_URL,
            EMAIL_VERIFICATION_TIMEOUT_HOURS="48",
        )

        self.assertTrue(values["REQUIRE_EMAIL_VERIFICATION"])
        self.assertEqual(values["FRONTEND_EMAIL_VERIFICATION_URL"], VERIFICATION_URL)
        self.assertEqual(values["EMAIL_VERIFICATION_TIMEOUT"], 48 * 3600)

    def test_invalid_verification_timeout_fails_to_start(self):
        result = run_manage_command(["check"], EMAIL_VERIFICATION_TIMEOUT_HOURS="-1")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EMAIL_VERIFICATION_TIMEOUT_HOURS", result.stderr)

    def test_resend_rate_comes_from_the_environment(self):
        values = read_settings(["REST_FRAMEWORK"], THROTTLE_VERIFY_EMAIL_RATE="2/h")

        self.assertEqual(
            values["REST_FRAMEWORK"]["DEFAULT_THROTTLE_RATES"]["verify_email"], "2/h"
        )

from unittest import mock

from anymail.exceptions import AnymailAPIError
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings

from core.checks import check_email_backend, check_email_provider_settings
from core.email_provider import (
    build_provider_backend,
    read_anymail_settings,
    validate_email_provider,
)
from core.emails import send_templated_email

from .settings_subprocess import read_settings, run_manage_command
from .test_emails import (
    RECIPIENT,
    TEMPLATE_PREFIX,
    SynchronousThread,
    with_test_templates,
)

TEST_BACKEND = "anymail.backends.test.EmailBackend"
RESEND_BACKEND = "anymail.backends.resend.EmailBackend"


class ReadAnymailSettingsTests(SimpleTestCase):
    def test_keeps_only_the_prefixed_variables_without_the_prefix(self):
        environment = {"ANYMAIL_RESEND_API_KEY": "key", "EMAIL_URL": "", "PATH": "/"}

        self.assertEqual(read_anymail_settings(environment), {"RESEND_API_KEY": "key"})

    def test_turns_true_and_false_into_booleans(self):
        environment = {
            "ANYMAIL_IGNORE_UNSUPPORTED_FEATURES": "True",
            "ANYMAIL_DEBUG_API_REQUESTS": "false",
        }

        self.assertEqual(
            read_anymail_settings(environment),
            {"IGNORE_UNSUPPORTED_FEATURES": True, "DEBUG_API_REQUESTS": False},
        )


class ValidateEmailProviderTests(SimpleTestCase):
    def test_accepts_an_installed_provider(self):
        for provider in (
            "mailgun",
            "resend",
            "brevo",
            "postmark",
            "amazon_ses",
            "test",
        ):
            with self.subTest(provider=provider):
                self.assertEqual(validate_email_provider(provider, ""), provider)

    def test_accepts_no_provider(self):
        self.assertEqual(validate_email_provider("", "smtp://smtp.example.com"), "")

    def test_rejects_an_unknown_provider(self):
        for provider in (
            "nope",
            "base",
            "base_requests",
            "resend.EmailBackend",
            "../x",
        ):
            with self.subTest(provider=provider):
                with self.assertRaisesRegex(ImproperlyConfigured, "EMAIL_PROVIDER"):
                    validate_email_provider(provider, "")

    def test_rejects_a_provider_together_with_an_smtp_url(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "EMAIL_URL"):
            validate_email_provider("resend", "smtp://smtp.example.com")

    def test_builds_the_backend_path(self):
        self.assertEqual(build_provider_backend("resend"), RESEND_BACKEND)


class EmailProviderSettingsTests(SimpleTestCase):
    def test_no_provider_keeps_the_email_url_backend(self):
        values = read_settings(["EMAIL_BACKEND"], EMAIL_PROVIDER="")

        self.assertEqual(
            values["EMAIL_BACKEND"], "django.core.mail.backends.smtp.EmailBackend"
        )

    def test_a_provider_selects_its_anymail_backend(self):
        values = read_settings(
            ["EMAIL_BACKEND", "ANYMAIL"],
            EMAIL_URL="",
            EMAIL_PROVIDER="resend",
            ANYMAIL_RESEND_API_KEY="test-key",
        )

        self.assertEqual(values["EMAIL_BACKEND"], RESEND_BACKEND)
        self.assertEqual(
            values["ANYMAIL"], {"RESEND_API_KEY": "test-key", "REQUESTS_TIMEOUT": 10}
        )

    def test_the_request_timeout_matches_the_smtp_one(self):
        values = read_settings(
            ["ANYMAIL"],
            EMAIL_URL="",
            EMAIL_PROVIDER="test",
            ANYMAIL_REQUESTS_TIMEOUT="99",
        )

        self.assertEqual(values["ANYMAIL"]["REQUESTS_TIMEOUT"], 10)

    def test_an_unknown_provider_fails_to_start(self):
        result = run_manage_command(["check"], EMAIL_URL="", EMAIL_PROVIDER="nope")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EMAIL_PROVIDER", result.stderr)

    def test_a_missing_api_key_stops_the_check(self):
        result = run_manage_command(["check"], EMAIL_URL="", EMAIL_PROVIDER="resend")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("core.E004", result.stderr)


class EmailProviderCheckTests(SimpleTestCase):
    def run_check(self, backend, anymail_settings):
        with override_settings(EMAIL_BACKEND=backend, ANYMAIL=anymail_settings):
            return [message.id for message in check_email_provider_settings(None)]

    def test_reports_a_provider_without_its_api_key(self):
        self.assertEqual(self.run_check(RESEND_BACKEND, {}), ["core.E004"])

    def test_accepts_a_provider_with_its_api_key(self):
        self.assertEqual(self.run_check(RESEND_BACKEND, {"RESEND_API_KEY": "k"}), [])

    def test_ignores_the_smtp_backend(self):
        smtp_backend = "django.core.mail.backends.smtp.EmailBackend"

        self.assertEqual(self.run_check(smtp_backend, {}), [])

    def test_names_the_missing_setting(self):
        with override_settings(EMAIL_BACKEND=RESEND_BACKEND, ANYMAIL={}):
            message = check_email_provider_settings(None)[0]

        self.assertIn("RESEND_API_KEY", message.msg)


class NonDeliveringProviderTests(SimpleTestCase):
    def test_deployed_environments_warn_with_the_test_and_console_providers(self):
        for backend in (TEST_BACKEND, "anymail.backends.console.EmailBackend"):
            with self.subTest(backend=backend):
                with override_settings(ENVIRONMENT="prod", EMAIL_BACKEND=backend):
                    ids = [message.id for message in check_email_backend(None)]
                self.assertEqual(ids, ["core.W004"])

    def test_a_real_provider_raises_nothing(self):
        with override_settings(ENVIRONMENT="prod", EMAIL_BACKEND=RESEND_BACKEND):
            self.assertEqual(check_email_backend(None), [])


@with_test_templates()
@override_settings(EMAIL_BACKEND=TEST_BACKEND, ANYMAIL={})
class AnymailDeliveryTests(TestCase):
    def send(self):
        send_templated_email(TEMPLATE_PREFIX, RECIPIENT, {"name": "Jane"})

    @override_settings(EMAIL_SEND_IN_BACKGROUND=False)
    def test_sends_through_the_provider(self):
        self.send()

        message = mail.outbox[-1]
        self.assertEqual(message.to, [RECIPIENT])
        self.assertEqual(message.anymail_status.status, {"sent"})

    @override_settings(EMAIL_SEND_IN_BACKGROUND=True)
    @mock.patch("core.emails.Thread", SynchronousThread)
    def test_logs_a_provider_failure_instead_of_raising(self):
        failure = AnymailAPIError("the provider answered 401")
        with mock.patch(
            "django.core.mail.EmailMultiAlternatives.send", side_effect=failure
        ):
            with self.assertLogs("core.emails", level="ERROR") as logs:
                with self.captureOnCommitCallbacks(execute=True):
                    self.send()

        self.assertIn(TEMPLATE_PREFIX, logs.output[0])
        self.assertNotIn(RECIPIENT, logs.output[0])

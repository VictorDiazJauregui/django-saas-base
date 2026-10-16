import smtplib
from pathlib import Path
from unittest import mock

from django.core import mail
from django.db import transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import translation

from core.emails import send_templated_email

from .settings_subprocess import read_settings, run_manage_command

TEST_TEMPLATES = Path(__file__).resolve().parent / "templates"
TEMPLATE_PREFIX = "test_emails/greeting"
RECIPIENT = "jane.doe@example.com"


def with_test_templates():
    template_settings = {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [TEST_TEMPLATES],
        "APP_DIRS": True,
    }
    return override_settings(
        TEMPLATES=[template_settings], DEFAULT_FROM_EMAIL="no-reply@example.com"
    )


class SynchronousThread:
    def __init__(self, target, args=()):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


@with_test_templates()
@override_settings(EMAIL_SEND_IN_BACKGROUND=False)
class TemplatedEmailTests(TestCase):
    def send(self):
        send_templated_email(TEMPLATE_PREFIX, RECIPIENT, {"name": "Jane"})
        return mail.outbox[-1]

    def test_sends_to_the_recipient_from_the_default_sender(self):
        message = self.send()

        self.assertEqual(message.to, [RECIPIENT])
        self.assertEqual(message.from_email, "no-reply@example.com")
        self.assertEqual(message.subject, "Password for Jane")

    def test_sends_a_text_body_and_an_html_alternative(self):
        message = self.send()

        self.assertEqual(message.body.strip(), "Password: Jane")
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn("<p>Password: Jane</p>", html)

    def test_renders_in_the_active_language(self):
        with translation.override("es"):
            message = self.send()

        self.assertEqual(message.subject, "Contraseña for Jane")
        self.assertIn("Contraseña: Jane", message.body)


@with_test_templates()
@override_settings(EMAIL_SEND_IN_BACKGROUND=True)
@mock.patch("core.emails.Thread", SynchronousThread)
class BackgroundEmailTests(TestCase):
    def send(self):
        send_templated_email(TEMPLATE_PREFIX, RECIPIENT, {"name": "Jane"})

    def test_waits_for_the_transaction_to_commit(self):
        with self.captureOnCommitCallbacks() as callbacks:
            self.send()
            self.assertEqual(len(mail.outbox), 0)

        for callback in callbacks:
            callback()
        self.assertEqual(len(mail.outbox), 1)

    def test_is_not_sent_when_the_transaction_rolls_back(self):
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError), transaction.atomic():
                self.send()
                raise RuntimeError("roll back")

        self.assertEqual(len(mail.outbox), 0)

    def test_renders_in_the_language_of_the_caller(self):
        with self.captureOnCommitCallbacks(execute=True), translation.override("es"):
            self.send()

        self.assertEqual(mail.outbox[0].subject, "Contraseña for Jane")

    def test_logs_a_delivery_failure_instead_of_raising(self):
        failure = smtplib.SMTPException("connection refused")
        with mock.patch(
            "django.core.mail.EmailMultiAlternatives.send", side_effect=failure
        ):
            with self.assertLogs("core.emails", level="ERROR") as logs:
                with self.captureOnCommitCallbacks(execute=True):
                    self.send()

        self.assertIn(TEMPLATE_PREFIX, logs.output[0])
        self.assertNotIn(RECIPIENT, logs.output[0])


class EmailSettingsTests(SimpleTestCase):
    def test_console_backend_by_default(self):
        values = read_settings(["EMAIL_BACKEND"], EMAIL_URL="")

        self.assertEqual(
            values["EMAIL_BACKEND"], "django.core.mail.backends.console.EmailBackend"
        )

    def test_reads_an_smtp_url_with_an_encoded_password(self):
        names = ["EMAIL_BACKEND", "EMAIL_HOST", "EMAIL_PORT", "EMAIL_HOST_USER"]
        names += [
            "EMAIL_HOST_PASSWORD",
            "EMAIL_USE_TLS",
            "EMAIL_USE_SSL",
            "EMAIL_TIMEOUT",
        ]
        url = "smtp+tls://apikey:p%40ss%23word@smtp.example.com:587"

        values = read_settings(names, EMAIL_URL=url)

        self.assertEqual(
            values["EMAIL_BACKEND"], "django.core.mail.backends.smtp.EmailBackend"
        )
        self.assertEqual(
            (values["EMAIL_HOST"], values["EMAIL_PORT"]), ("smtp.example.com", 587)
        )
        self.assertEqual(values["EMAIL_HOST_USER"], "apikey")
        self.assertEqual(values["EMAIL_HOST_PASSWORD"], "p@ss#word")
        self.assertTrue(values["EMAIL_USE_TLS"])
        self.assertFalse(values["EMAIL_USE_SSL"])
        self.assertEqual(values["EMAIL_TIMEOUT"], 10)

    def test_unknown_scheme_fails_to_start(self):
        result = run_manage_command(["check"], EMAIL_URL="foo://smtp.example.com")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("foo", result.stderr)

    def test_reads_the_default_sender(self):
        values = read_settings(
            ["DEFAULT_FROM_EMAIL"], DEFAULT_FROM_EMAIL="hi@example.com"
        )

        self.assertEqual(values["DEFAULT_FROM_EMAIL"], "hi@example.com")

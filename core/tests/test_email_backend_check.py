from django.test import SimpleTestCase, override_settings

NON_DELIVERING_BACKENDS = (
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
)
SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"


def run_check(environment, backend):
    from core.checks import check_email_backend

    with override_settings(ENVIRONMENT=environment, EMAIL_BACKEND=backend):
        return [message.id for message in check_email_backend(None)]


class EmailBackendCheckTests(SimpleTestCase):
    def test_deployed_environments_warn_when_emails_are_not_delivered(self):
        for environment in ("staging", "prod"):
            for backend in NON_DELIVERING_BACKENDS:
                with self.subTest(environment=environment, backend=backend):
                    self.assertEqual(run_check(environment, backend), ["core.W004"])

    def test_smtp_raises_nothing(self):
        for environment in ("staging", "prod"):
            with self.subTest(environment=environment):
                self.assertEqual(run_check(environment, SMTP_BACKEND), [])

    def test_development_environments_raise_nothing(self):
        for environment in ("local", "ci"):
            for backend in NON_DELIVERING_BACKENDS:
                with self.subTest(environment=environment, backend=backend):
                    self.assertEqual(run_check(environment, backend), [])

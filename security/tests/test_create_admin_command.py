import os
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.test import TestCase

from .user_factory import DEFAULT_PASSWORD, create_superuser, create_user

User = get_user_model()

ADMIN_EMAIL = "bootstrap.admin@example.com"
ADMIN_ENVIRONMENT = {"ADMIN_EMAIL": ADMIN_EMAIL, "ADMIN_PASSWORD": DEFAULT_PASSWORD}
NEW_PASSWORD = "Rotated-Passphrase-77"


def admin_environment(**overrides):
    return mock.patch.dict(os.environ, {**ADMIN_ENVIRONMENT, **overrides})


def run_command(*arguments):
    output = StringIO()
    call_command("create_admin_auto", *arguments, stdout=output, stderr=output)
    return output.getvalue()


class CreateAdminAutoCommandTests(TestCase):
    @mock.patch.dict(os.environ, ADMIN_ENVIRONMENT)
    def test_creates_superuser_from_environment(self):
        call_command("create_admin_auto", stdout=mock.Mock())

        admin_user = User.objects.get(email=ADMIN_EMAIL)
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.check_password(DEFAULT_PASSWORD))

    @mock.patch.dict(os.environ, ADMIN_ENVIRONMENT)
    def test_keeps_single_superuser_when_run_twice(self):
        call_command("create_admin_auto", stdout=mock.Mock())
        call_command("create_admin_auto", stdout=mock.Mock())

        self.assertEqual(User.objects.filter(email=ADMIN_EMAIL).count(), 1)

    @mock.patch.dict(os.environ, {**ADMIN_ENVIRONMENT, "ADMIN_PASSWORD": ""})
    def test_requires_credentials_in_environment(self):
        with self.assertRaises(ImproperlyConfigured):
            call_command("create_admin_auto", stdout=mock.Mock())


class PasswordPolicyTests(TestCase):
    def test_rejects_weak_passwords_without_creating_the_user(self):
        for password in ("123", "change-me"):
            with (
                self.subTest(password=password),
                admin_environment(ADMIN_PASSWORD=password),
            ):
                with self.assertRaisesMessage(CommandError, "ADMIN_PASSWORD"):
                    run_command()

        self.assertFalse(User.objects.filter(email=ADMIN_EMAIL).exists())

    @admin_environment(ADMIN_PASSWORD="Bootstrap#2026")
    def test_rejects_a_password_similar_to_the_email(self):
        with self.assertRaisesMessage(CommandError, "too similar"):
            run_command()

    @admin_environment(ADMIN_PASSWORD="123")
    def test_lists_the_reasons_of_the_rejection(self):
        with self.assertRaises(CommandError) as raised:
            run_command()

        self.assertIn("too short", str(raised.exception))


class ExistingUserTests(TestCase):
    @admin_environment()
    def test_reports_an_existing_superuser_and_keeps_its_password(self):
        create_superuser(email=ADMIN_EMAIL, password=NEW_PASSWORD)

        output = run_command()

        self.assertIn("already exists", output)
        self.assertTrue(
            User.objects.get(email=ADMIN_EMAIL).check_password(NEW_PASSWORD)
        )

    @admin_environment(ADMIN_EMAIL=ADMIN_EMAIL.upper())
    def test_matches_the_existing_superuser_ignoring_case(self):
        create_superuser(email=ADMIN_EMAIL)

        run_command()

        self.assertEqual(User.objects.filter(email__iexact=ADMIN_EMAIL).count(), 1)

    @admin_environment()
    def test_fails_for_a_regular_user_without_promoting_it(self):
        create_user(email=ADMIN_EMAIL)

        with self.assertRaisesMessage(CommandError, "is not a superuser"):
            run_command()

        self.assertFalse(User.objects.get(email=ADMIN_EMAIL).is_superuser)


class UpdatePasswordTests(TestCase):
    @admin_environment(ADMIN_PASSWORD=NEW_PASSWORD)
    def test_rotates_the_password_of_the_superuser(self):
        create_superuser(email=ADMIN_EMAIL, password=DEFAULT_PASSWORD)

        output = run_command("--update-password")

        admin_user = User.objects.get(email=ADMIN_EMAIL)
        self.assertIn("updated", output)
        self.assertTrue(admin_user.check_password(NEW_PASSWORD))
        self.assertFalse(admin_user.check_password(DEFAULT_PASSWORD))

    @admin_environment()
    def test_is_idempotent_when_the_password_already_matches(self):
        create_superuser(email=ADMIN_EMAIL, password=DEFAULT_PASSWORD)

        first_output = run_command("--update-password")
        second_output = run_command("--update-password")

        self.assertIn("unchanged", first_output)
        self.assertEqual(first_output, second_output)

    @admin_environment(ADMIN_PASSWORD="123")
    def test_keeps_the_old_password_when_the_new_one_is_weak(self):
        create_superuser(email=ADMIN_EMAIL, password=DEFAULT_PASSWORD)

        with self.assertRaises(CommandError):
            run_command("--update-password")

        self.assertTrue(
            User.objects.get(email=ADMIN_EMAIL).check_password(DEFAULT_PASSWORD)
        )

    @admin_environment(ADMIN_PASSWORD=NEW_PASSWORD)
    def test_creates_the_superuser_when_it_does_not_exist(self):
        output = run_command("--update-password")

        self.assertIn("created", output)
        self.assertTrue(User.objects.get(email=ADMIN_EMAIL).is_superuser)

    @admin_environment(ADMIN_PASSWORD=NEW_PASSWORD)
    def test_fails_for_a_regular_user_without_changing_it(self):
        create_user(email=ADMIN_EMAIL)

        with self.assertRaisesMessage(CommandError, "is not a superuser"):
            run_command("--update-password")

        self.assertTrue(
            User.objects.get(email=ADMIN_EMAIL).check_password(DEFAULT_PASSWORD)
        )


class SecretHandlingTests(TestCase):
    def test_never_prints_the_password(self):
        scenarios = (
            (NEW_PASSWORD, ()),
            (NEW_PASSWORD, ()),
            ("Bootstrap#2026", ()),
            (NEW_PASSWORD, ("--update-password",)),
        )
        for password, arguments in scenarios:
            with self.subTest(password=password, arguments=arguments):
                self.assertNotIn(password, self.capture_output(password, arguments))

    def capture_output(self, password, arguments):
        with admin_environment(ADMIN_PASSWORD=password):
            try:
                return run_command(*arguments)
            except CommandError as error:
                return str(error)

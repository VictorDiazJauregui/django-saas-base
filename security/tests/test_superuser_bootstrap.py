from django.contrib.auth import get_user_model
from django.test import TestCase

from security.superuser_bootstrap import (
    BootstrapOutcome,
    SuperuserBootstrapError,
    ensure_superuser,
    rotate_superuser_password,
)

from .user_factory import DEFAULT_PASSWORD, create_superuser, create_user

User = get_user_model()

ADMIN_EMAIL = "bootstrap.admin@example.com"
NEW_PASSWORD = "Rotated-Passphrase-77"


class EnsureSuperuserTests(TestCase):
    def test_creates_a_missing_superuser(self):
        outcome = ensure_superuser(ADMIN_EMAIL, DEFAULT_PASSWORD)

        self.assertEqual(outcome, BootstrapOutcome.CREATED)
        self.assertTrue(User.objects.get(email=ADMIN_EMAIL).is_superuser)

    def test_stores_the_email_normalized(self):
        ensure_superuser("  Bootstrap.Admin@Example.COM ", DEFAULT_PASSWORD)

        self.assertTrue(User.objects.filter(email=ADMIN_EMAIL).exists())

    def test_leaves_an_existing_superuser_untouched(self):
        create_superuser(email=ADMIN_EMAIL, password=DEFAULT_PASSWORD)

        outcome = ensure_superuser(ADMIN_EMAIL.upper(), NEW_PASSWORD)

        self.assertEqual(outcome, BootstrapOutcome.ALREADY_EXISTS)
        self.assertTrue(
            User.objects.get(email=ADMIN_EMAIL).check_password(DEFAULT_PASSWORD)
        )

    def test_refuses_to_promote_a_regular_user(self):
        create_user(email=ADMIN_EMAIL)

        with self.assertRaisesMessage(SuperuserBootstrapError, "is not a superuser"):
            ensure_superuser(ADMIN_EMAIL, DEFAULT_PASSWORD)

        self.assertFalse(User.objects.get(email=ADMIN_EMAIL).is_superuser)

    def test_rejects_a_password_that_breaks_the_policy(self):
        for password in ("123", "change-me", "Bootstrap#2026"):
            with self.subTest(password=password):
                with self.assertRaises(SuperuserBootstrapError):
                    ensure_superuser(ADMIN_EMAIL, password)

        self.assertFalse(User.objects.filter(email=ADMIN_EMAIL).exists())


class RotateSuperuserPasswordTests(TestCase):
    def test_changes_the_password_of_an_existing_superuser(self):
        create_superuser(email=ADMIN_EMAIL, password=DEFAULT_PASSWORD)

        outcome = rotate_superuser_password(ADMIN_EMAIL, NEW_PASSWORD)

        self.assertEqual(outcome, BootstrapOutcome.UPDATED)
        self.assertTrue(
            User.objects.get(email=ADMIN_EMAIL).check_password(NEW_PASSWORD)
        )

    def test_reports_an_unchanged_password(self):
        create_superuser(email=ADMIN_EMAIL, password=DEFAULT_PASSWORD)

        outcome = rotate_superuser_password(ADMIN_EMAIL, DEFAULT_PASSWORD)

        self.assertEqual(outcome, BootstrapOutcome.UNCHANGED)

    def test_creates_the_superuser_when_it_does_not_exist(self):
        outcome = rotate_superuser_password(ADMIN_EMAIL, NEW_PASSWORD)

        self.assertEqual(outcome, BootstrapOutcome.CREATED)
        self.assertTrue(User.objects.get(email=ADMIN_EMAIL).is_superuser)

    def test_keeps_the_old_password_when_the_new_one_is_weak(self):
        create_superuser(email=ADMIN_EMAIL, password=DEFAULT_PASSWORD)

        with self.assertRaises(SuperuserBootstrapError):
            rotate_superuser_password(ADMIN_EMAIL, "123")

        self.assertTrue(
            User.objects.get(email=ADMIN_EMAIL).check_password(DEFAULT_PASSWORD)
        )

    def test_refuses_to_rotate_a_regular_user(self):
        create_user(email=ADMIN_EMAIL)

        with self.assertRaisesMessage(SuperuserBootstrapError, "is not a superuser"):
            rotate_superuser_password(ADMIN_EMAIL, NEW_PASSWORD)

        regular_user = User.objects.get(email=ADMIN_EMAIL)
        self.assertFalse(regular_user.is_superuser)
        self.assertTrue(regular_user.check_password(DEFAULT_PASSWORD))

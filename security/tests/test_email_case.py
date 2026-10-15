import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from .api_test_case import CacheResetAPITestCase
from .user_factory import (
    DEFAULT_EMAIL,
    DEFAULT_PASSWORD,
    build_registration_payload,
    create_superuser,
    create_user,
)

User = get_user_model()

REGISTER_URL = reverse("security:register")
LOGIN_URL = reverse("security:login")
ADD_USER_URL = reverse("admin:security_user_add")
DUPLICATE_EMAIL_MESSAGE = "user with this email address already exists."
UPPERCASE_EMAIL = DEFAULT_EMAIL.upper()


def count_mailbox_rows(email):
    return User.objects.filter(email__iexact=email).count()


class RegistrationEmailCaseTests(CacheResetAPITestCase):
    def test_rejects_the_same_mailbox_in_other_case(self):
        create_user()
        payload = build_registration_payload(email=UPPERCASE_EMAIL)

        response = self.client.post(REGISTER_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["email"], [DUPLICATE_EMAIL_MESSAGE])
        self.assertEqual(count_mailbox_rows(DEFAULT_EMAIL), 1)

    def test_stores_the_email_in_lowercase_without_spaces(self):
        payload = build_registration_payload(email=f"  {UPPERCASE_EMAIL}  ")

        response = self.client.post(REGISTER_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], DEFAULT_EMAIL)
        self.assertTrue(User.objects.filter(email=DEFAULT_EMAIL).exists())


class LoginEmailCaseTests(CacheResetAPITestCase):
    @classmethod
    def setUpTestData(cls):
        create_user()

    def test_logs_in_with_the_email_in_other_case(self):
        credentials = {"email": UPPERCASE_EMAIL, "password": DEFAULT_PASSWORD}

        response = self.client.post(LOGIN_URL, credentials, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_rejects_a_wrong_password_with_the_email_in_other_case(self):
        credentials = {"email": UPPERCASE_EMAIL, "password": "Wrong-Passphrase-42"}

        response = self.client.post(LOGIN_URL, credentials, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserEmailNormalizationTests(TestCase):
    def test_create_user_stores_the_email_in_lowercase(self):
        user = create_user(email=f" {UPPERCASE_EMAIL} ")

        self.assertEqual(user.email, DEFAULT_EMAIL)

    def test_save_stores_the_email_in_lowercase(self):
        user = User(email=UPPERCASE_EMAIL)
        user.save()

        user.refresh_from_db()
        self.assertEqual(user.email, DEFAULT_EMAIL)

    def test_database_rejects_the_same_mailbox_in_other_case(self):
        create_user()
        other_user = create_user(email="other.member@example.com")

        with self.assertRaises(IntegrityError):
            User.objects.filter(pk=other_user.pk).update(email=UPPERCASE_EMAIL)


class AdminEmailCaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = create_superuser()
        create_user()

    def test_add_form_rejects_the_same_mailbox_in_other_case(self):
        self.client.force_login(self.superuser)
        form_data = {
            "email": UPPERCASE_EMAIL,
            "password1": DEFAULT_PASSWORD,
            "password2": DEFAULT_PASSWORD,
        }

        response = self.client.post(ADD_USER_URL, form_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        form_errors = response.context["adminform"].form.errors
        self.assertEqual(list(form_errors), ["email"])
        self.assertEqual(len(form_errors["email"]), 1)
        self.assertEqual(count_mailbox_rows(DEFAULT_EMAIL), 1)

    def test_add_form_requires_a_staff_session(self):
        response = self.client.get(ADD_USER_URL)

        self.assertRedirects(response, f"{reverse('admin:login')}?next={ADD_USER_URL}")


class CreateAdminAutoEmailCaseTests(TestCase):
    environment = {
        "ADMIN_EMAIL": "Bootstrap.Admin@Example.COM",
        "ADMIN_PASSWORD": DEFAULT_PASSWORD,
    }

    @mock.patch.dict(os.environ, environment)
    def test_finds_the_existing_superuser_when_the_email_has_upper_case(self):
        call_command("create_admin_auto", stdout=mock.Mock())
        call_command("create_admin_auto", stdout=mock.Mock())

        self.assertEqual(count_mailbox_rows("bootstrap.admin@example.com"), 1)

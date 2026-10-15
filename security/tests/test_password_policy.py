from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .user_factory import build_registration_payload, create_superuser

User = get_user_model()

REGISTER_URL = reverse("security:register")
ADD_USER_URL = reverse("admin:security_user_add")
NO_SYMBOL_PASSWORD = "Kestrel9Quartz"


def register_with_password(client, password, **overrides):
    payload = build_registration_payload(
        password=password, password2=password, **overrides
    )
    return client.post(REGISTER_URL, payload, format="json")


class RegistrationPasswordPolicyTests(APITestCase):
    def test_rejects_a_password_similar_to_the_email(self):
        response = register_with_password(
            self.client, "juanperez", email="juanperez@example.com", first_name="Juan"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "The password is too similar to the email address.",
            response.data["password"],
        )
        self.assertFalse(User.objects.filter(email="juanperez@example.com").exists())

    def test_rejects_a_password_without_symbol(self):
        response = register_with_password(self.client, NO_SYMBOL_PASSWORD)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(response.data["password"]), 1)

    def test_returns_every_broken_rule_at_once(self):
        response = register_with_password(self.client, "kestrel")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(response.data["password"]), 4)

    def test_accepts_a_password_that_meets_every_rule(self):
        response = register_with_password(self.client, "Kestrel9Quartz!")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class AdminPasswordPolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = create_superuser()

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_add_form_rejects_a_password_without_symbol(self):
        form_data = {
            "email": "new.member@example.com",
            "password1": NO_SYMBOL_PASSWORD,
            "password2": NO_SYMBOL_PASSWORD,
        }

        response = self.client.post(ADD_USER_URL, form_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("password2", response.context["adminform"].form.errors)
        self.assertFalse(User.objects.filter(email="new.member@example.com").exists())

    def test_add_form_shows_the_character_rules_in_the_help_text(self):
        response = self.client.get(ADD_USER_URL)

        self.assertContains(response, "uppercase letter (A-Z)")

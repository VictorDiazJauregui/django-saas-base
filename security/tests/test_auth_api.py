from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .user_factory import (
    DEFAULT_EMAIL,
    DEFAULT_PASSWORD,
    build_registration_payload,
    create_user,
)

User = get_user_model()

REGISTER_URL = reverse("security:register")
LOGIN_URL = reverse("security:login")
REFRESH_URL = reverse("security:token_refresh")


class UserRegistrationTests(APITestCase):
    def test_registers_user_with_hashed_password(self):
        response = self.client.post(
            REGISTER_URL, build_registration_payload(), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email=DEFAULT_EMAIL)
        self.assertTrue(user.check_password(DEFAULT_PASSWORD))

    def test_never_returns_passwords(self):
        response = self.client.post(
            REGISTER_URL, build_registration_payload(), format="json"
        )

        self.assertNotIn("password", response.data)
        self.assertNotIn("password2", response.data)

    def test_rejects_mismatched_passwords(self):
        payload = build_registration_payload(password2="An0ther-Passphrase-42")

        response = self.client.post(REGISTER_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.exists())

    def test_rejects_duplicated_email(self):
        create_user()

        response = self.client.post(
            REGISTER_URL, build_registration_payload(), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)


class LoginTests(APITestCase):
    def setUp(self):
        create_user()

    def test_returns_token_pair_for_valid_credentials(self):
        credentials = {"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD}

        response = self.client.post(LOGIN_URL, credentials, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_rejects_invalid_credentials(self):
        credentials = {"email": DEFAULT_EMAIL, "password": "wrong-passphrase"}

        response = self.client.post(LOGIN_URL, credentials, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TokenRefreshTests(APITestCase):
    def setUp(self):
        create_user()

    def test_returns_new_access_token(self):
        credentials = {"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD}
        refresh_token = self.client.post(LOGIN_URL, credentials, format="json").data[
            "refresh"
        ]

        response = self.client.post(
            REFRESH_URL, {"refresh": refresh_token}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_rejects_invalid_refresh_token(self):
        response = self.client.post(
            REFRESH_URL, {"refresh": "not-a-token"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

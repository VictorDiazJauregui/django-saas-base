import uuid

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken

from .api_test_case import CacheResetAPITestCase
from .user_factory import (
    DEFAULT_EMAIL,
    DEFAULT_PASSWORD,
    build_registration_payload,
    create_user,
)

LOGIN_URL = reverse("security:login")
REFRESH_URL = reverse("security:token_refresh")
REGISTER_URL = reverse("security:register")


def build_access_token_for(user_id):
    token = AccessToken()
    token["user_id"] = str(user_id)
    return str(token)


class UserPrimaryKeyTests(TestCase):
    def test_primary_key_is_a_uuid(self):
        user = create_user()

        self.assertIsInstance(user.pk, uuid.UUID)

    def test_users_created_in_a_row_get_unrelated_ids(self):
        first = create_user(email="first@example.com")
        second = create_user(email="second@example.com")

        self.assertIsInstance(second.pk, uuid.UUID)
        self.assertNotEqual(first.pk, second.pk)


class TokenUserIdTests(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user()

    def log_in(self):
        credentials = {"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD}
        return self.client.post(LOGIN_URL, credentials, format="json")

    def test_access_token_carries_the_user_uuid(self):
        access = AccessToken(self.log_in().data["access"])

        self.assertEqual(uuid.UUID(access["user_id"]), self.user.pk)

    def test_refreshed_access_token_keeps_the_user_uuid(self):
        refresh = self.log_in().data["refresh"]

        response = self.client.post(REFRESH_URL, {"refresh": refresh}, format="json")

        access = AccessToken(response.data["access"])
        self.assertEqual(uuid.UUID(access["user_id"]), self.user.pk)

    def test_rejects_a_token_whose_user_does_not_exist(self):
        token = build_access_token_for(uuid.uuid4())
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.post(
            REGISTER_URL, build_registration_payload(email="x@example.com")
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_accepts_a_token_of_an_existing_user(self):
        token = build_access_token_for(self.user.pk)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.post(
            REGISTER_URL, build_registration_payload(email="x@example.com")
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .api_test_case import CacheResetAPITestCase
from .user_factory import DEFAULT_EMAIL, DEFAULT_PASSWORD, create_user

LOGIN_URL = reverse("security:login")
REFRESH_URL = reverse("security:token_refresh")


def lifetime_of(token):
    return token["exp"] - token["iat"]


class TokenRotationTestCase(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user()

    def obtain_refresh_token(self):
        payload = {"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD}
        response = self.client.post(LOGIN_URL, payload, format="json")
        return response.data["refresh"]

    def refresh(self, refresh_token):
        return self.client.post(REFRESH_URL, {"refresh": refresh_token}, format="json")


class RefreshRotationTests(TokenRotationTestCase):
    def test_refresh_returns_a_new_refresh_token(self):
        old_refresh = self.obtain_refresh_token()

        response = self.refresh(old_refresh)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {"access", "refresh"})
        self.assertNotEqual(response.data["refresh"], old_refresh)

    def test_reusing_a_refresh_token_is_rejected(self):
        old_refresh = self.obtain_refresh_token()
        self.refresh(old_refresh)

        response = self.refresh(old_refresh)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "token_not_valid")

    def test_the_rotated_refresh_token_works(self):
        rotated_refresh = self.refresh(self.obtain_refresh_token()).data["refresh"]

        response = self.refresh(rotated_refresh)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_used_refresh_token_is_blacklisted(self):
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

        old_refresh = self.obtain_refresh_token()
        self.refresh(old_refresh)

        jti = RefreshToken(old_refresh, verify=False)["jti"]
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=jti).exists())


class RefreshErrorTests(TokenRotationTestCase):
    def test_malformed_token_is_unauthorized(self):
        response = self.refresh("not-a-token")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_token_is_a_bad_request(self):
        response = self.client.post(REFRESH_URL, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_is_not_allowed(self):
        response = self.client.get(REFRESH_URL)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_refresh_endpoint_needs_no_access_token(self):
        self.client.credentials()

        response = self.refresh(self.obtain_refresh_token())

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_refresh_of_a_deleted_user_is_unauthorized(self):
        refresh_token = self.obtain_refresh_token()
        self.user.delete()

        response = self.refresh(refresh_token)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "no_active_account")


class TokenLifetimeTests(TokenRotationTestCase):
    def test_default_lifetimes_match_the_previous_behaviour(self):
        refresh_token = RefreshToken(self.obtain_refresh_token(), verify=False)

        self.assertEqual(lifetime_of(refresh_token.access_token), 5 * 60)
        self.assertEqual(lifetime_of(refresh_token), 24 * 60 * 60)

    # SimpleJWT copies the lifetimes into the token classes at import time, so
    # override_settings can't change them: the values per variable are covered in
    # core/tests/test_production_settings.py, in a subprocess.
    def test_tokens_use_the_configured_lifetimes(self):
        self.assertEqual(
            AccessToken.lifetime, settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
        )
        self.assertEqual(
            RefreshToken.lifetime, settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
        )

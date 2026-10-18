import os
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from security.token_revocation import revoke_refresh_tokens

from .api_test_case import CacheResetAPITestCase
from .user_factory import DEFAULT_EMAIL, DEFAULT_PASSWORD, create_superuser, create_user

User = get_user_model()

LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/login/refresh/"
NEW_PASSWORD = "Changed-Passphrase-88"


def is_blacklisted(refresh_token):
    jti = RefreshToken(str(refresh_token), verify=False)["jti"]
    return BlacklistedToken.objects.filter(token__jti=jti).exists()


class RevokeRefreshTokensTests(TestCase):
    def setUp(self):
        self.user = create_user()

    def test_revokes_every_pending_refresh_token(self):
        tokens = [RefreshToken.for_user(self.user) for _ in range(2)]

        revoked = revoke_refresh_tokens(self.user)

        self.assertEqual(revoked, 2)
        self.assertTrue(all(is_blacklisted(token) for token in tokens))

    def test_skips_expired_and_already_revoked_tokens(self):
        expired = RefreshToken.for_user(self.user)
        OutstandingToken.objects.filter(jti=expired["jti"]).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        RefreshToken.for_user(self.user).blacklist()

        revoked = revoke_refresh_tokens(self.user)

        self.assertEqual(revoked, 0)
        self.assertFalse(is_blacklisted(expired))

    def test_leaves_other_users_tokens_alone(self):
        other_token = RefreshToken.for_user(create_user(email="other@example.com"))

        revoke_refresh_tokens(self.user)

        self.assertFalse(is_blacklisted(other_token))


class PasswordChangeTestCase(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user()

    def obtain_refresh_token(self, password=DEFAULT_PASSWORD):
        payload = {"email": DEFAULT_EMAIL, "password": password}
        return self.client.post(LOGIN_URL, payload, format="json").data["refresh"]

    def refresh_status(self, refresh_token):
        response = self.client.post(
            REFRESH_URL, {"refresh": refresh_token}, format="json"
        )
        return response.status_code


class PasswordChangeRevocationTests(PasswordChangeTestCase):
    def test_admin_password_change_revokes_open_sessions(self):
        sessions = [self.obtain_refresh_token() for _ in range(2)]
        self.client.force_login(create_superuser())

        self.client.post(
            f"/admin/security/user/{self.user.pk}/password/",
            {"password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        for refresh_token in sessions:
            self.assertEqual(
                self.refresh_status(refresh_token), status.HTTP_401_UNAUTHORIZED
            )

    @mock.patch("getpass.getpass", return_value=NEW_PASSWORD)
    def test_changepassword_command_revokes_open_sessions(self, _getpass):
        refresh_token = self.obtain_refresh_token()

        call_command("changepassword", DEFAULT_EMAIL, stdout=StringIO())

        self.assertEqual(
            self.refresh_status(refresh_token), status.HTTP_401_UNAUTHORIZED
        )

    def test_create_admin_auto_rotation_revokes_open_sessions(self):
        self.user.delete()
        self.user = create_superuser(email=DEFAULT_EMAIL)
        refresh_token = self.obtain_refresh_token()
        environment = {"ADMIN_EMAIL": DEFAULT_EMAIL, "ADMIN_PASSWORD": NEW_PASSWORD}

        with mock.patch.dict(os.environ, environment):
            call_command("create_admin_auto", "--update-password", stdout=StringIO())

        self.assertEqual(
            self.refresh_status(refresh_token), status.HTTP_401_UNAUTHORIZED
        )

    def test_assigning_a_new_hash_revokes_open_sessions(self):
        refresh_token = self.obtain_refresh_token()
        user = User.objects.get(pk=self.user.pk)

        user.password = make_password(NEW_PASSWORD)
        user.save()

        self.assertEqual(
            self.refresh_status(refresh_token), status.HTTP_401_UNAUTHORIZED
        )


class UnchangedPasswordTests(PasswordChangeTestCase):
    def test_saving_without_a_password_change_keeps_sessions(self):
        refresh_token = self.obtain_refresh_token()
        user = User.objects.get(pk=self.user.pk)

        user.first_name = "Renamed"
        user.save()

        self.assertEqual(self.refresh_status(refresh_token), status.HTTP_200_OK)

    def test_creating_a_user_revokes_nothing(self):
        create_user(email="new.user@example.com")

        self.assertFalse(BlacklistedToken.objects.exists())

    def test_sessions_opened_after_the_change_survive_later_saves(self):
        user = User.objects.get(pk=self.user.pk)
        user.set_password(NEW_PASSWORD)
        user.save()
        refresh_token = self.obtain_refresh_token(password=NEW_PASSWORD)

        user.last_name = "Renamed"
        user.save()

        self.assertEqual(self.refresh_status(refresh_token), status.HTTP_200_OK)

    def test_reloaded_user_does_not_revoke_again_on_save(self):
        stale_user = User.objects.get(pk=self.user.pk)
        changed_user = User.objects.get(pk=self.user.pk)
        changed_user.set_password(NEW_PASSWORD)
        changed_user.save()
        refresh_token = self.obtain_refresh_token(password=NEW_PASSWORD)

        stale_user.refresh_from_db()
        stale_user.first_name = "Renamed"
        stale_user.save()

        self.assertEqual(self.refresh_status(refresh_token), status.HTTP_200_OK)

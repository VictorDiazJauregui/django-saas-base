from datetime import timedelta

from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from security.api_keys import (
    authenticate_api_key,
    hash_api_key,
    issue_api_key,
    revoke_api_keys,
)
from security.authentication import ApiKeyAuthentication
from security.models import ApiKey, AuditLog
from security.permissions import HasRole

from .api_test_case import CacheResetAPITestCase
from .test_permissions import build_view
from .user_factory import create_user

ROLE = "integrations"


def api_key_header(raw_key):
    return {"HTTP_AUTHORIZATION": f"Api-Key {raw_key}"}


class ApiKeyAuthenticationHeaderTests(TestCase):
    def test_asks_for_an_api_key(self):
        request = APIRequestFactory().get("/api/v1/auth/me/")

        self.assertEqual(ApiKeyAuthentication().authenticate_header(request), "Api-Key")


class IssueApiKeyTests(TestCase):
    def setUp(self):
        self.user = create_user()

    def test_stores_only_the_hash_and_a_visible_prefix(self):
        api_key, raw_key = issue_api_key(self.user, "billing server")

        self.assertTrue(raw_key.startswith(f"{api_key.prefix}."))
        self.assertEqual(api_key.key_hash, hash_api_key(raw_key))
        self.assertNotIn(raw_key.partition(".")[2], api_key.key_hash)
        self.assertEqual(len(api_key.prefix), 12)

    def test_is_shown_by_name_and_prefix(self):
        api_key = issue_api_key(self.user, "billing server")[0]

        self.assertEqual(str(api_key), f"billing server ({api_key.prefix})")

    def test_every_key_is_different(self):
        first = issue_api_key(self.user, "a")[1]
        second = issue_api_key(self.user, "b")[1]

        self.assertNotEqual(first, second)


class AuthenticateApiKeyTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.api_key, self.raw_key = issue_api_key(self.user, "billing server")

    def assertRejected(self, raw_key):
        with self.assertRaises(AuthenticationFailed) as caught:
            authenticate_api_key(raw_key)
        self.assertEqual(caught.exception.get_codes(), "invalid_api_key")

    def test_a_valid_key_returns_its_record_and_marks_the_use(self):
        api_key = authenticate_api_key(self.raw_key)

        self.assertEqual(api_key.user, self.user)
        self.api_key.refresh_from_db()
        self.assertIsNotNone(self.api_key.last_used_at)

    def test_a_wrong_secret_with_a_real_prefix_is_rejected(self):
        self.assertRejected(f"{self.api_key.prefix}.not-the-secret")

    def test_an_unknown_or_malformed_key_is_rejected(self):
        for raw_key in ("unknown.secret", "no-separator", "", "."):
            with self.subTest(raw_key=raw_key):
                self.assertRejected(raw_key)

    def test_a_revoked_key_is_rejected(self):
        revoke_api_keys(ApiKey.objects.filter(pk=self.api_key.pk))

        self.assertRejected(self.raw_key)

    def test_an_expired_key_is_rejected(self):
        ApiKey.objects.filter(pk=self.api_key.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        self.assertRejected(self.raw_key)

    def test_a_key_that_has_not_expired_yet_works(self):
        ApiKey.objects.filter(pk=self.api_key.pk).update(
            expires_at=timezone.now() + timedelta(days=1)
        )

        self.assertEqual(authenticate_api_key(self.raw_key).user, self.user)

    def test_the_key_of_an_inactive_user_is_rejected(self):
        self.user.is_active = False
        self.user.save()

        self.assertRejected(self.raw_key)

    def test_revoking_twice_keeps_the_first_date(self):
        keys = ApiKey.objects.filter(pk=self.api_key.pk)
        self.assertEqual(revoke_api_keys(keys), 1)
        first_revocation = keys.get().revoked_at

        self.assertEqual(revoke_api_keys(keys), 0)
        self.assertEqual(keys.get().revoked_at, first_revocation)


@override_settings(API_KEYS_ENABLED=True)
class ApiKeyRequestTests(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user()
        self.api_key, self.raw_key = issue_api_key(self.user, "billing server")

    def get_profile(self, headers):
        return self.client.get(reverse("security:me"), **headers)

    def test_a_valid_key_acts_as_its_user(self):
        response = self.get_profile(api_key_header(self.raw_key))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)

    def test_an_invalid_key_gets_401_with_its_code(self):
        response = self.get_profile(api_key_header(f"{self.api_key.prefix}.wrong"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "invalid_api_key")

    def test_a_header_without_the_key_gets_401(self):
        response = self.get_profile({"HTTP_AUTHORIZATION": "Api-Key"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "invalid_api_key")

    def test_a_header_with_extra_parts_gets_401(self):
        response = self.get_profile({"HTTP_AUTHORIZATION": f"Api-Key {self.raw_key} x"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_header_is_still_anonymous(self):
        response = self.get_profile({})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "not_authenticated")

    def test_the_keyword_ignores_case(self):
        response = self.get_profile({"HTTP_AUTHORIZATION": f"api-key {self.raw_key}"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_the_bearer_token_keeps_working(self):
        login = self.client.post(
            reverse("security:login"),
            {"email": self.user.email, "password": "Str0ng-Passphrase-42"},
            format="json",
        )
        headers = {"HTTP_AUTHORIZATION": f"Bearer {login.data['access']}"}

        self.assertEqual(self.get_profile(headers).status_code, status.HTTP_200_OK)

    def test_the_audit_log_records_the_key_owner_and_not_the_key(self):
        self.client.patch(
            reverse("security:me"),
            {"first_name": "Integration"},
            format="json",
            **api_key_header(self.raw_key),
        )

        record = AuditLog.objects.get(path=reverse("security:me"))
        self.assertEqual(record.user, self.user)
        self.assertNotIn(self.raw_key, str(record.payload))


@override_settings(API_KEYS_ENABLED=False)
class DisabledApiKeyTests(CacheResetAPITestCase):
    def test_the_header_is_ignored_as_before(self):
        raw_key = issue_api_key(create_user(), "billing server")[1]

        response = self.client.get(reverse("security:me"), **api_key_header(raw_key))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "not_authenticated")


@override_settings(API_KEYS_ENABLED=True)
class ApiKeyPermissionTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.raw_key = issue_api_key(self.user, "billing server")[1]
        self.view = build_view(HasRole(ROLE))

    def call_with_key(self):
        request = APIRequestFactory().get(
            "/api/v1/protected/", **api_key_header(self.raw_key)
        )
        return self.view(request)

    def test_a_key_without_the_role_is_forbidden(self):
        self.assertEqual(self.call_with_key().status_code, status.HTTP_403_FORBIDDEN)

    def test_a_key_whose_user_has_the_role_passes(self):
        self.user.groups.add(Group.objects.create(name=ROLE))

        self.assertEqual(self.call_with_key().status_code, status.HTTP_200_OK)

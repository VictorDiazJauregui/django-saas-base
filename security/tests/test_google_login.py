from unittest import mock

import jwt
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from jwt import PyJWKClientConnectionError
from rest_framework import status

from core.environment import GOOGLE_JWKS_URL, validate_google_jwks_url
from security.google_login import build_jwks_client
from security.models import AuditLog, ExternalIdentity
from webhooks.models import WebhookDelivery, WebhookEndpoint

from .api_test_case import LanguageResetAPITestCase
from .google_tokens import (
    FOREIGN_KEY,
    SUBJECT,
    build_jwks,
    sign_id_token,
    with_google_login,
)
from .test_throttling import override_rates
from .two_factor_helpers import enable_two_factor, with_two_factor
from .user_factory import (
    DEFAULT_EMAIL,
    DEFAULT_PASSWORD,
    create_superuser,
    create_user,
)

User = get_user_model()
GOOGLE_URL = reverse("security:google_login")


@with_google_login()
@override_rates(login=None)
class GoogleLoginTestCase(LanguageResetAPITestCase):
    # The client keeps the keys it fetched: a fresh one per test sees each test's mock.
    def setUp(self):
        super().setUp()
        build_jwks_client.cache_clear()
        patcher = mock.patch("jwt.PyJWKClient.fetch_data", return_value=build_jwks())
        self.fetch = patcher.start()
        self.addCleanup(patcher.stop)

    def log_in_with_google(self, id_token=None, **claims):
        token = id_token or sign_id_token(**claims)
        return self.client.post(GOOGLE_URL, {"id_token": token}, format="json")


class NewAccountTests(GoogleLoginTestCase):
    def test_creates_a_verified_account_and_returns_the_tokens(self):
        response = self.log_in_with_google()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {"access", "refresh"})
        user = User.objects.get(email=DEFAULT_EMAIL)
        self.assertTrue(user.is_email_verified)
        self.assertFalse(user.has_usable_password())
        self.assertEqual((user.first_name, user.last_name), ("Jane", "Doe"))
        self.assertTrue(
            ExternalIdentity.objects.filter(
                user=user, provider="google", subject=SUBJECT
            ).exists()
        )

    @override_settings(WEBHOOKS_ENABLED=True)
    def test_a_new_account_emits_user_registered_and_a_link_does_not(self):
        WebhookEndpoint.objects.create(
            url="https://hooks.example.com/in", events=["user.registered"], secret="s"
        )
        create_user(email="linked@example.com")

        self.log_in_with_google()
        self.log_in_with_google(email="linked@example.com", sub="another-subject")

        self.assertEqual(
            list(WebhookDelivery.objects.values_list("payload__email", flat=True)),
            [DEFAULT_EMAIL],
        )

    def test_a_new_account_does_not_need_a_vouched_address(self):
        response = self.log_in_with_google(hd=None)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_the_email_is_stored_lowercase(self):
        self.log_in_with_google(email="Jane.Doe@Example.com")

        self.assertTrue(User.objects.filter(email=DEFAULT_EMAIL).exists())

    def test_the_second_login_uses_the_same_account(self):
        self.log_in_with_google()
        response = self.log_in_with_google(email="new.address@example.com")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.count(), 1)

    @override_settings(ALLOW_PUBLIC_REGISTRATION=False)
    def test_closed_registration_refuses_a_new_email(self):
        response = self.log_in_with_google()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "permission_denied")
        self.assertFalse(User.objects.exists())

    def test_the_audit_log_records_the_user_and_hides_the_token(self):
        self.log_in_with_google()

        record = AuditLog.objects.get(path=GOOGLE_URL)
        self.assertEqual(record.user.email, DEFAULT_EMAIL)
        self.assertEqual(record.payload["id_token"], "[REDACTED]")


class LinkedIdentityAdminTests(GoogleLoginTestCase):
    def test_the_user_page_shows_the_google_link_read_only(self):
        self.log_in_with_google()
        user = User.objects.get(email=DEFAULT_EMAIL)
        self.client.force_login(create_superuser())

        response = self.client.get(
            reverse("admin:security_user_change", args=[user.pk])
        )

        self.assertContains(response, SUBJECT)
        self.assertNotContains(response, "external_identities-0-subject")


class ExistingAccountTests(GoogleLoginTestCase):
    def test_links_a_verified_account_and_keeps_its_password(self):
        user = create_user()

        response = self.log_in_with_google()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password(DEFAULT_PASSWORD))
        self.assertEqual(user.external_identities.get().subject, SUBJECT)

    @override_settings(ALLOW_PUBLIC_REGISTRATION=False)
    def test_links_an_existing_account_even_with_closed_registration(self):
        create_user()

        self.assertEqual(self.log_in_with_google().status_code, status.HTTP_200_OK)

    def test_an_unverified_account_loses_the_password_of_whoever_registered_it(self):
        squatter = create_user()
        squatter.is_email_verified = False
        squatter.save()
        refresh = self.client.post(
            reverse("security:login"),
            {"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD},
            format="json",
        ).data.get("refresh")

        self.log_in_with_google()

        squatter.refresh_from_db()
        self.assertTrue(squatter.is_email_verified)
        self.assertFalse(squatter.has_usable_password())
        self.assertIsNotNone(refresh)
        reuse = self.client.post(
            reverse("security:token_refresh"), {"refresh": refresh}, format="json"
        )
        self.assertEqual(reuse.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_gmail_address_links_without_a_workspace_domain(self):
        create_user(email="jane.doe@gmail.com")

        response = self.log_in_with_google(email="jane.doe@gmail.com", hd=None)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(ExternalIdentity.objects.exists())

    def test_an_address_google_does_not_vouch_for_does_not_take_an_account(self):
        user = create_user()

        response = self.log_in_with_google(hd=None)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "account_exists")
        self.assertFalse(ExternalIdentity.objects.exists())
        user.refresh_from_db()
        self.assertTrue(user.check_password(DEFAULT_PASSWORD))

    def test_an_unverified_account_keeps_its_password_without_a_vouched_address(self):
        squatter = create_user()
        squatter.is_email_verified = False
        squatter.save()

        response = self.log_in_with_google(hd=None)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        squatter.refresh_from_db()
        self.assertFalse(squatter.is_email_verified)

    def test_an_inactive_account_gets_401(self):
        user = create_user()
        user.is_active = False
        user.save()

        response = self.log_in_with_google()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "no_active_account")

    @with_two_factor()
    def test_an_account_with_two_factor_gets_the_challenge(self):
        enable_two_factor(self.client, create_user())

        response = self.log_in_with_google()

        self.assertEqual(set(response.data), {"mfa_required", "mfa_token"})


class InvalidTokenTests(GoogleLoginTestCase):
    def assertInvalid(self, response):
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "invalid_google_token")

    def test_a_token_signed_with_another_key_is_rejected(self):
        self.assertInvalid(self.log_in_with_google(sign_id_token(FOREIGN_KEY)))

    def test_an_expired_token_is_rejected(self):
        self.assertInvalid(self.log_in_with_google(exp=1, iat=0))

    def test_a_token_for_another_client_is_rejected(self):
        self.assertInvalid(
            self.log_in_with_google(aud="other.apps.googleusercontent.com")
        )

    def test_a_token_from_another_issuer_is_rejected(self):
        self.assertInvalid(self.log_in_with_google(iss="https://evil.example.com"))

    def test_the_short_issuer_is_accepted(self):
        response = self.log_in_with_google(iss="accounts.google.com")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_an_unverified_google_email_is_rejected(self):
        self.assertInvalid(self.log_in_with_google(email_verified=False))

    def test_garbage_is_rejected(self):
        self.assertInvalid(self.log_in_with_google("not-a-jwt"))

    def test_an_unsigned_token_is_rejected(self):
        unsigned = jwt.encode({"sub": SUBJECT}, key=None, algorithm="none")

        self.assertInvalid(self.log_in_with_google(unsigned))

    def test_a_missing_token_gets_400(self):
        response = self.client.post(GOOGLE_URL, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("id_token", response.data["fields"])

    def test_google_down_gets_503(self):
        self.fetch.side_effect = PyJWKClientConnectionError("timed out")

        response = self.log_in_with_google()

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["code"], "google_unavailable")


@with_google_login(client_ids=())
class DisabledGoogleLoginTests(LanguageResetAPITestCase):
    def test_the_route_answers_404(self):
        response = self.client.post(GOOGLE_URL, {"id_token": "x"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class JwksUrlValidationTests(SimpleTestCase):
    def test_google_url_is_accepted_everywhere(self):
        for environment in ("local", "ci", "staging", "prod"):
            with self.subTest(environment=environment):
                self.assertEqual(
                    validate_google_jwks_url(GOOGLE_JWKS_URL, environment),
                    GOOGLE_JWKS_URL,
                )

    def test_another_url_is_accepted_only_in_development(self):
        local_url = "http://localhost:9999/jwks.json"
        self.assertEqual(validate_google_jwks_url(local_url, "local"), local_url)
        for environment in ("staging", "prod"):
            with self.subTest(environment=environment):
                with self.assertRaisesRegex(ImproperlyConfigured, "GOOGLE_JWKS_URL"):
                    validate_google_jwks_url(local_url, environment)

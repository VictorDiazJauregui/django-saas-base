from datetime import datetime, timedelta
from unittest import mock

from django.contrib.auth.tokens import (
    PasswordResetTokenGenerator,
    default_token_generator,
)
from django.core import mail
from django.test import override_settings
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from security.models import AuditLog
from security.redaction import REDACTED_PLACEHOLDER

from .account_links import FRONTEND, find_link, read_link_parameters, with_account_links
from .api_test_case import CacheResetAPITestCase
from .test_throttling import WRONG_PASSWORD, override_rates
from .user_factory import DEFAULT_EMAIL, DEFAULT_PASSWORD, create_user

RESET_URL = "/api/v1/auth/password/reset/"
CONFIRM_URL = "/api/v1/auth/password/reset/confirm/"
LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/login/refresh/"
NEW_PASSWORD = "Changed-Passphrase-88"
UNKNOWN_EMAIL = "nobody@example.com"


@with_account_links()
@override_rates(login=None, password=None)
class PasswordResetTestCase(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user()

    def request_reset(self, email=DEFAULT_EMAIL):
        return self.client.post(RESET_URL, {"email": email}, format="json")

    def emailed_link(self):
        self.request_reset()
        return read_link_parameters(mail.outbox[-1])

    def confirm(self, link, password=NEW_PASSWORD, confirmation=None):
        payload = {
            **link,
            "new_password": password,
            "new_password2": confirmation or password,
        }
        return self.client.post(CONFIRM_URL, payload, format="json")

    def log_in(self, password):
        payload = {"email": DEFAULT_EMAIL, "password": password}
        return self.client.post(LOGIN_URL, payload, format="json")

    def valid_link(self, user=None):
        user = user or self.user
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        return {"uid": uid, "token": default_token_generator.make_token(user)}


class PasswordResetRequestTests(PasswordResetTestCase):
    def test_existing_email_gets_a_link_to_the_frontend(self):
        response = self.request_reset()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [DEFAULT_EMAIL])
        uid = read_link_parameters(mail.outbox[0])["uid"]
        self.assertEqual(force_str(urlsafe_base64_decode(uid)), str(self.user.pk))

    def test_unknown_email_gets_the_same_answer_and_no_email(self):
        known = self.request_reset()
        unknown = self.request_reset(UNKNOWN_EMAIL)

        self.assertEqual(unknown.status_code, known.status_code)
        self.assertEqual(unknown.data, known.data)
        self.assertEqual(len(mail.outbox), 1)

    def test_inactive_user_gets_no_email(self):
        self.user.is_active = False
        self.user.save()

        response = self.request_reset()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(mail.outbox, [])

    def test_user_without_a_usable_password_gets_no_email(self):
        self.user.set_unusable_password()
        self.user.save()

        self.request_reset()

        self.assertEqual(mail.outbox, [])

    def test_email_in_other_case_finds_the_account(self):
        self.request_reset(DEFAULT_EMAIL.upper())

        self.assertEqual(mail.outbox[0].to, [DEFAULT_EMAIL])

    @override_settings(
        FRONTEND_PASSWORD_RESET_URL=f"{FRONTEND}/r/{{uid}}/{{token}}?lang=es&x={{other}}"
    )
    def test_only_the_two_markers_of_the_url_are_replaced(self):
        link = self.valid_link()

        self.request_reset()

        expected = f"{FRONTEND}/r/{link['uid']}/"
        self.assertTrue(find_link(mail.outbox[0]).startswith(expected))
        self.assertTrue(find_link(mail.outbox[0]).endswith("?lang=es&x={other}"))

    def test_a_stale_token_in_the_header_is_ignored(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer expired-or-garbage")

        response = self.request_reset()

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_email_is_rejected(self):
        response = self.request_reset("not-an-email")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["fields"])

    @override_rates(password="1/h")
    def test_the_password_scope_limits_the_requests(self):
        self.request_reset(UNKNOWN_EMAIL)

        response = self.request_reset(UNKNOWN_EMAIL)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class PasswordResetConfirmTests(PasswordResetTestCase):
    def test_link_of_the_email_sets_the_new_password(self):
        response = self.confirm(self.emailed_link())

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.log_in(NEW_PASSWORD).status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.log_in(DEFAULT_PASSWORD).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_revokes_the_refresh_tokens(self):
        refresh = str(RefreshToken.for_user(self.user))

        self.confirm(self.emailed_link())

        response = self.client.post(REFRESH_URL, {"refresh": refresh}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unlocks_an_account_locked_by_failed_logins(self):
        for _ in range(5):
            self.log_in(WRONG_PASSWORD)
        locked = self.log_in(DEFAULT_PASSWORD)

        self.confirm(self.emailed_link())

        self.assertEqual(locked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(self.log_in(NEW_PASSWORD).status_code, status.HTTP_200_OK)

    def test_audit_stores_the_user_of_the_confirm_only(self):
        self.confirm(self.emailed_link())

        request_record = AuditLog.objects.get(path=RESET_URL)
        confirm_record = AuditLog.objects.get(path=CONFIRM_URL)
        self.assertIsNone(request_record.user)
        self.assertEqual(confirm_record.user, self.user)
        for field in ("token", "new_password", "new_password2"):
            self.assertEqual(confirm_record.payload[field], REDACTED_PLACEHOLDER)

    def test_weak_password_is_rejected(self):
        response = self.confirm(self.emailed_link(), password="12345678")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data["fields"])

    def test_mismatched_confirmation_is_rejected(self):
        response = self.confirm(self.emailed_link(), confirmation="Other-Passphrase-77")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password2", response.data["fields"])


class PasswordResetInvalidLinkTests(PasswordResetTestCase):
    def assert_invalid_link(self, link):
        response = self.confirm(link)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(list(response.data["fields"]), ["token"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(DEFAULT_PASSWORD))
        return response.data

    def test_link_works_only_once(self):
        link = self.emailed_link()
        self.confirm(link)

        response = self.confirm(link, password="Third-Passphrase-99")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(list(response.data["fields"]), ["token"])

    def test_expired_link_is_rejected(self):
        link = self.valid_link()
        later = datetime.now() + timedelta(hours=2)

        with mock.patch.object(PasswordResetTokenGenerator, "_now", return_value=later):
            self.assert_invalid_link(link)

    def test_every_broken_link_gets_the_same_error(self):
        link = self.valid_link()
        other_user = create_user(email="other@example.com")
        broken_links = (
            {**link, "token": link["token"][:-2] + "zz"},
            {**link, "uid": "not-a-uid"},
            {**link, "uid": urlsafe_base64_encode(force_bytes("not-a-uuid"))},
            {**link, "uid": self.valid_link(other_user)["uid"]},
        )

        errors = [self.assert_invalid_link(broken) for broken in broken_links]

        self.assertTrue(all(error == errors[0] for error in errors))

    def test_missing_uid_and_token_are_rejected(self):
        response = self.confirm({})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("uid", response.data["fields"])
        self.assertIn("token", response.data["fields"])

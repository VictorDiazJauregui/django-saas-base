import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status

from security.models import AuditLog
from security.redaction import REDACTED_PLACEHOLDER

from .account_links import read_link_parameters, with_account_links
from .api_test_case import CacheResetAPITestCase
from .test_throttling import WRONG_PASSWORD, override_rates
from .user_factory import (
    DEFAULT_EMAIL,
    DEFAULT_PASSWORD,
    build_registration_payload,
    create_superuser,
    create_user,
)

User = get_user_model()

REGISTER_URL = "/api/v1/auth/register/"
LOGIN_URL = "/api/v1/auth/login/"
VERIFY_URL = "/api/v1/auth/verify-email/"
RESEND_URL = "/api/v1/auth/verify-email/resend/"
UNKNOWN_EMAIL = "nobody@example.com"


def verification_link(user, issued_at=None):
    from security.email_verification import build_verification_token

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    if issued_at is None:
        return {"uid": uid, "token": build_verification_token(user)}
    with mock.patch("django.core.signing.time.time", return_value=issued_at):
        return {"uid": uid, "token": build_verification_token(user)}


@with_account_links()
@override_settings(REQUIRE_EMAIL_VERIFICATION=True)
@override_rates(login=None, register=None, verify_email=None)
class EmailVerificationTestCase(CacheResetAPITestCase):
    def register(self, email=DEFAULT_EMAIL):
        payload = build_registration_payload(email=email)
        return self.client.post(REGISTER_URL, payload, format="json")

    def log_in(self, password=DEFAULT_PASSWORD, email=DEFAULT_EMAIL):
        payload = {"email": email, "password": password}
        return self.client.post(LOGIN_URL, payload, format="json")

    def verify(self, link):
        return self.client.post(VERIFY_URL, link, format="json")

    def resend(self, email=DEFAULT_EMAIL):
        return self.client.post(RESEND_URL, {"email": email}, format="json")

    def registered_user(self):
        self.register()
        return User.objects.get(email=DEFAULT_EMAIL)


class RegistrationWithVerificationTests(EmailVerificationTestCase):
    def test_new_account_is_active_but_unverified(self):
        user = self.registered_user()

        self.assertTrue(user.is_active)
        self.assertFalse(user.is_email_verified)

    def test_registration_sends_the_verification_link(self):
        self.register()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [DEFAULT_EMAIL])
        self.assertEqual(set(read_link_parameters(mail.outbox[0])), {"uid", "token"})

    def test_unverified_account_cannot_log_in(self):
        self.register()

        response = self.log_in()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unverified_login_looks_like_a_wrong_password(self):
        self.register()

        unverified = self.log_in()
        wrong_password = self.log_in(WRONG_PASSWORD)

        self.assertEqual(unverified.status_code, wrong_password.status_code)
        self.assertEqual(unverified.data, wrong_password.data)

    def test_link_of_the_email_verifies_the_account(self):
        self.register()

        response = self.verify(read_link_parameters(mail.outbox[0]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(User.objects.get(email=DEFAULT_EMAIL).is_email_verified)
        self.assertEqual(self.log_in().status_code, status.HTTP_200_OK)

    def test_turning_the_flag_off_lets_pending_accounts_in(self):
        self.register()

        with override_settings(REQUIRE_EMAIL_VERIFICATION=False):
            response = self.log_in()

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_audit_hides_the_verification_token(self):
        self.register()
        self.verify(read_link_parameters(mail.outbox[0]))

        record = AuditLog.objects.get(path=VERIFY_URL)
        self.assertEqual(record.payload["token"], REDACTED_PLACEHOLDER)


class VerificationLinkTests(EmailVerificationTestCase):
    def assert_invalid_link(self, link):
        response = self.verify(link)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(list(response.data["fields"]), ["token"])
        return response.data

    def test_link_works_only_once(self):
        user = self.registered_user()
        link = verification_link(user)
        self.verify(link)

        self.assert_invalid_link(link)

    def test_expired_link_is_rejected(self):
        user = self.registered_user()
        two_days_ago = time.time() - 2 * 24 * 3600

        self.assert_invalid_link(verification_link(user, issued_at=two_days_ago))
        self.assertFalse(User.objects.get(pk=user.pk).is_email_verified)

    def test_every_broken_link_gets_the_same_error(self):
        user = self.registered_user()
        other = create_user(email="other@example.com")
        link = verification_link(user)
        broken_links = (
            {**link, "token": link["token"][:-2] + "zz"},
            {**link, "uid": "not-a-uid"},
            {**link, "uid": verification_link(other)["uid"]},
        )

        errors = [self.assert_invalid_link(broken) for broken in broken_links]

        self.assertTrue(all(error == errors[0] for error in errors))
        self.assertFalse(User.objects.get(pk=user.pk).is_email_verified)

    def test_user_deactivated_by_the_admin_is_not_reactivated(self):
        user = create_user(email="disabled@example.com")
        User.objects.filter(pk=user.pk).update(is_active=False, is_email_verified=False)
        user.refresh_from_db()

        resend = self.resend(user.email)
        self.assert_invalid_link(verification_link(user))

        self.assertEqual(resend.status_code, status.HTTP_200_OK)
        self.assertEqual(mail.outbox, [])
        self.assertFalse(User.objects.get(pk=user.pk).is_active)


class ResendVerificationTests(EmailVerificationTestCase):
    def test_pending_account_gets_a_new_link(self):
        self.register()

        response = self.resend()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(
            self.verify(read_link_parameters(mail.outbox[1])).status_code, 204
        )

    def test_answer_is_the_same_for_pending_verified_and_unknown(self):
        self.register()
        create_user(email="verified@example.com")

        answers = [
            self.resend(email)
            for email in (DEFAULT_EMAIL, "verified@example.com", UNKNOWN_EMAIL)
        ]

        self.assertTrue(all(answer.data == answers[0].data for answer in answers))
        self.assertEqual([message.to for message in mail.outbox[1:]], [[DEFAULT_EMAIL]])

    @override_rates(verify_email="1/h")
    def test_the_verify_email_scope_limits_the_requests(self):
        self.resend(UNKNOWN_EMAIL)

        response = self.resend(UNKNOWN_EMAIL)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


@with_account_links()
@override_settings(REQUIRE_EMAIL_VERIFICATION=False)
@override_rates(register=None)
class RegistrationWithoutVerificationTests(CacheResetAPITestCase):
    def test_new_account_is_verified_and_logs_in(self):
        self.client.post(REGISTER_URL, build_registration_payload(), format="json")

        response = self.client.post(
            LOGIN_URL,
            {"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.get(email=DEFAULT_EMAIL).is_email_verified)
        self.assertEqual(mail.outbox, [])

    def test_users_created_outside_the_registration_are_verified(self):
        self.assertTrue(create_user().is_email_verified)
        self.assertTrue(create_superuser().is_email_verified)

    def test_the_admin_lists_and_filters_the_verification(self):
        self.client.force_login(create_superuser())

        response = self.client.get(reverse("admin:security_user_changelist"))

        self.assertContains(response, "column-is_email_verified")
        self.assertContains(response, "is_email_verified__exact")

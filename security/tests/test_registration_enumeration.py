from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core import mail
from django.test import override_settings
from rest_framework import status

from security.models import UserManager

from .account_links import with_account_links
from .api_test_case import CacheResetAPITestCase
from .test_throttling import override_rates
from .user_factory import (
    DEFAULT_EMAIL,
    DEFAULT_PASSWORD,
    build_registration_payload,
    create_user,
)

User = get_user_model()

REGISTER_URL = "/api/v1/auth/register/"
INTRUDER_PASSWORD = "Intruder-Passphrase-31"


def intruder_payload(email):
    return build_registration_payload(
        email=email,
        password=INTRUDER_PASSWORD,
        password2=INTRUDER_PASSWORD,
        first_name="Intruder",
    )


@with_account_links()
@override_rates(register=None)
class RegistrationEnumerationTests(CacheResetAPITestCase):
    def register(self, payload):
        return self.client.post(REGISTER_URL, payload, format="json")

    def test_existing_email_gets_the_same_answer_as_a_new_one(self):
        new_account = self.register(intruder_payload("fresh@example.com"))
        create_user()

        existing = self.register(intruder_payload(DEFAULT_EMAIL.upper()))

        self.assertEqual(existing.status_code, status.HTTP_201_CREATED)
        self.assertEqual(existing.status_code, new_account.status_code)
        self.assertEqual(existing.data, {**new_account.data, "email": DEFAULT_EMAIL})

    def test_existing_account_is_left_untouched(self):
        owner = create_user()

        self.register(intruder_payload(DEFAULT_EMAIL))

        owner.refresh_from_db()
        self.assertTrue(owner.check_password(DEFAULT_PASSWORD))
        self.assertEqual(owner.first_name, "")
        self.assertEqual(User.objects.filter(email__iexact=DEFAULT_EMAIL).count(), 1)

    def test_owner_is_warned_by_email(self):
        create_user()

        self.register(intruder_payload(DEFAULT_EMAIL))

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [DEFAULT_EMAIL])

    def test_new_account_without_verification_gets_no_email(self):
        self.register(build_registration_payload())

        self.assertEqual(mail.outbox, [])

    def test_duplicate_still_hashes_the_submitted_password(self):
        create_user()

        with mock.patch(
            "security.registration.make_password", wraps=make_password
        ) as hasher:
            self.register(intruder_payload(DEFAULT_EMAIL))

        hasher.assert_called_once_with(INTRUDER_PASSWORD)

    def test_concurrent_registration_is_answered_as_a_duplicate(self):
        create_user()

        with mock.patch.object(UserManager, "is_email_taken", return_value=False):
            response = self.register(intruder_payload(DEFAULT_EMAIL))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.filter(email__iexact=DEFAULT_EMAIL).count(), 1)
        self.assertEqual(mail.outbox[0].to, [DEFAULT_EMAIL])

    def test_invalid_payload_is_still_rejected(self):
        create_user()
        payload = {**intruder_payload(DEFAULT_EMAIL), "password2": "Other-Passphrase-1"}

        response = self.register(payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(mail.outbox, [])

    @override_settings(ALLOW_PUBLIC_REGISTRATION=False)
    def test_closed_registration_still_answers_403(self):
        create_user()

        response = self.register(intruder_payload(DEFAULT_EMAIL))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(mail.outbox, [])

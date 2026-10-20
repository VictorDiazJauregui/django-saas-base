from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from security.email_verification import build_verification_token
from security.frontend_links import encode_user_id
from security.tests.account_links import with_account_links
from security.tests.api_test_case import LanguageResetAPITestCase
from security.tests.test_throttling import override_rates
from security.tests.user_factory import (
    DEFAULT_EMAIL,
    build_registration_payload,
    create_user,
)
from webhooks.models import WebhookDelivery, WebhookEndpoint


def subscribe(*events):
    return WebhookEndpoint.objects.create(
        url="https://hooks.example.com/in", events=list(events), secret="s"
    )


@override_settings(
    WEBHOOKS_ENABLED=True,
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
@override_rates(register=None, verify_email=None)
class AccountEventTests(LanguageResetAPITestCase):
    def register(self):
        return self.client.post(
            reverse("security:register"), build_registration_payload(), format="json"
        )

    def test_a_public_registration_emits_user_registered(self):
        subscribe("user.registered")

        self.assertEqual(self.register().status_code, status.HTTP_201_CREATED)

        delivery = WebhookDelivery.objects.get()
        self.assertEqual(delivery.event, "user.registered")
        self.assertEqual(delivery.payload["email"], DEFAULT_EMAIL)
        self.assertIn("user_id", delivery.payload)

    def test_a_duplicate_registration_emits_nothing(self):
        create_user()
        subscribe("user.registered")

        self.register()

        self.assertFalse(WebhookDelivery.objects.exists())

    def test_a_user_created_elsewhere_emits_nothing(self):
        subscribe("user.registered")

        create_user()

        self.assertFalse(WebhookDelivery.objects.exists())

    @with_account_links()
    @override_settings(REQUIRE_EMAIL_VERIFICATION=True)
    def test_verifying_the_email_emits_user_email_verified(self):
        subscribe("user.email_verified")
        user = create_user()
        user.is_email_verified = False
        user.save()

        response = self.client.post(
            reverse("security:verify_email"),
            {"uid": encode_user_id(user), "token": build_verification_token(user)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        delivery = WebhookDelivery.objects.get()
        self.assertEqual(delivery.event, "user.email_verified")

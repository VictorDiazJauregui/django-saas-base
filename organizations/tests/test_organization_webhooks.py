from django.test import TestCase, override_settings

from organizations.organization_webhooks import (
    WebhookEndpointLimitReached,
    create_organization_webhook_endpoint,
    rotate_webhook_endpoint_secret,
)
from webhooks.models import WebhookEndpoint

from .organization_factory import create_organization

DETAILS = {
    "url": "https://hooks.example.com/in",
    "events": ["organization.member_added"],
}


@override_settings(WEBHOOK_ORGANIZATION_ENDPOINT_LIMIT=2)
class OrganizationWebhookEndpointCreationTests(TestCase):
    def setUp(self):
        self.organization = create_organization("Acme")

    def test_the_endpoint_belongs_to_the_organization_and_gets_a_secret(self):
        endpoint = create_organization_webhook_endpoint(self.organization, DETAILS)
        self.assertEqual(endpoint.organization, self.organization)
        self.assertGreaterEqual(len(endpoint.secret), 40)

    def test_the_limit_counts_inactive_endpoints(self):
        create_organization_webhook_endpoint(self.organization, DETAILS)
        create_organization_webhook_endpoint(
            self.organization, {**DETAILS, "is_active": False}
        )
        with self.assertRaises(WebhookEndpointLimitReached):
            create_organization_webhook_endpoint(self.organization, DETAILS)
        self.assertEqual(WebhookEndpoint.objects.count(), 2)

    def test_the_limit_is_counted_per_organization(self):
        create_organization_webhook_endpoint(self.organization, DETAILS)
        create_organization_webhook_endpoint(self.organization, DETAILS)
        other = create_organization("Globex")
        create_organization_webhook_endpoint(other, DETAILS)
        self.assertEqual(other.webhook_endpoints.count(), 1)

    def test_platform_endpoints_do_not_count(self):
        WebhookEndpoint.objects.create(secret="platform", **DETAILS)
        WebhookEndpoint.objects.create(secret="platform", **DETAILS)
        create_organization_webhook_endpoint(self.organization, DETAILS)
        self.assertEqual(self.organization.webhook_endpoints.count(), 1)


class WebhookSecretRotationTests(TestCase):
    def test_rotating_changes_only_the_secret(self):
        organization = create_organization("Acme")
        endpoint = create_organization_webhook_endpoint(organization, DETAILS)
        old_secret = endpoint.secret
        rotate_webhook_endpoint_secret(endpoint)
        endpoint.refresh_from_db()
        self.assertNotEqual(endpoint.secret, old_secret)
        self.assertEqual(endpoint.url, DETAILS["url"])
        self.assertEqual(endpoint.organization, organization)

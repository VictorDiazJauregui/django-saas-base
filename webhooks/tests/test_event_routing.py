import uuid

from django.test import TestCase, override_settings

from organizations.models import Organization
from organizations.tests.organization_factory import create_organization
from webhooks.events import emit_webhook_event
from webhooks.models import WebhookDelivery, WebhookEndpoint

EVENT = "organization.member_removed"


def create_endpoint(
    organization: Organization | None = None, events=(EVENT,), **fields
) -> WebhookEndpoint:
    return WebhookEndpoint.objects.create(
        url="https://hooks.example.com/in",
        events=list(events),
        secret="test-secret",
        organization=organization,
        **fields,
    )


def receiving_endpoints() -> set[uuid.UUID]:
    return set(WebhookDelivery.objects.values_list("endpoint_id", flat=True))


@override_settings(WEBHOOKS_ENABLED=True, TENANCY_ENABLED=True)
class EventRoutingTests(TestCase):
    def setUp(self):
        self.acme = create_organization("Acme")
        self.globex = create_organization("Globex")
        self.platform = create_endpoint()
        self.acme_endpoint = create_endpoint(self.acme)
        self.globex_endpoint = create_endpoint(self.globex)

    def test_event_without_organization_reaches_only_platform_endpoints(self):
        emit_webhook_event(EVENT, {"user_id": "1"})
        self.assertEqual(receiving_endpoints(), {self.platform.pk})

    def test_event_of_an_organization_reaches_platform_and_that_organization(self):
        emit_webhook_event(EVENT, {"user_id": "1"}, organization=self.acme)
        self.assertEqual(
            receiving_endpoints(), {self.platform.pk, self.acme_endpoint.pk}
        )

    def test_event_of_one_organization_never_reaches_another(self):
        emit_webhook_event(EVENT, {"user_id": "1"}, organization=self.globex)
        self.assertNotIn(self.acme_endpoint.pk, receiving_endpoints())

    def test_platform_event_never_reaches_a_subscribed_organization(self):
        create_endpoint(self.acme, events=["user.registered"])
        emit_webhook_event("user.registered", {"user_id": "1"})
        self.assertEqual(receiving_endpoints(), set())

    def test_inactive_organization_endpoint_receives_nothing(self):
        self.acme_endpoint.is_active = False
        self.acme_endpoint.save()
        emit_webhook_event(EVENT, {"user_id": "1"}, organization=self.acme)
        self.assertEqual(receiving_endpoints(), {self.platform.pk})

    def test_existing_two_argument_calls_keep_working(self):
        self.assertEqual(emit_webhook_event(EVENT, {"user_id": "1"}), 1)

    def test_organization_is_only_accepted_by_name(self):
        with self.assertRaises(TypeError):
            emit_webhook_event(EVENT, {"user_id": "1"}, self.acme)

    @override_settings(TENANCY_ENABLED=False)
    def test_organization_endpoints_receive_nothing_with_tenancy_off(self):
        emit_webhook_event(EVENT, {"user_id": "1"}, organization=self.acme)
        self.assertEqual(receiving_endpoints(), {self.platform.pk})

    @override_settings(WEBHOOKS_ENABLED=False)
    def test_nothing_is_stored_with_webhooks_off(self):
        emit_webhook_event(EVENT, {"user_id": "1"}, organization=self.acme)
        self.assertFalse(WebhookDelivery.objects.exists())


class WebhookKeyTests(TestCase):
    def test_endpoints_and_deliveries_use_random_ids(self):
        endpoint = create_endpoint()
        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint, event=EVENT, payload={}
        )
        self.assertIsInstance(endpoint.pk, uuid.UUID)
        self.assertIsInstance(delivery.pk, uuid.UUID)

    def test_deleting_the_organization_deletes_its_endpoints(self):
        organization = create_organization("Acme")
        create_endpoint(organization)
        organization.delete()
        self.assertFalse(WebhookEndpoint.objects.exists())

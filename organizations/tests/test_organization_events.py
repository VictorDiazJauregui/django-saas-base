from django.db import transaction
from django.test import TestCase, override_settings

from organizations.membership_changes import remove_member_as
from organizations.organization_creation import create_organization_for
from security.tests.user_factory import create_user
from webhooks.models import WebhookDelivery, WebhookEndpoint

from .organization_factory import create_member, create_organization

EVENTS = ["organization.created", "organization.member_removed"]


class RollbackRequested(Exception):
    pass


@override_settings(WEBHOOKS_ENABLED=True)
class OrganizationEventTests(TestCase):
    def setUp(self):
        WebhookEndpoint.objects.create(
            url="https://hooks.example.com/in", events=EVENTS, secret="test-secret"
        )
        self.owner = create_user("owner@example.com")

    def test_creating_an_organization_emits_created(self):
        organization = create_organization_for(self.owner, {"name": "Acme"})
        delivery = WebhookDelivery.objects.get()
        self.assertEqual(delivery.event, "organization.created")
        expected = {
            "organization_id": str(organization.pk),
            "name": "Acme",
            "slug": "acme",
            "owner_id": str(self.owner.pk),
            "owner_email": "owner@example.com",
        }
        self.assertEqual(delivery.payload, expected)

    def test_removing_a_member_emits_member_removed(self):
        organization = create_organization("Acme")
        actor = create_member(organization, "owner@example.org", "owner")
        member = create_member(organization, "member@example.com", "admin")
        remove_member_as(actor, member)
        delivery = WebhookDelivery.objects.get()
        self.assertEqual(delivery.event, "organization.member_removed")
        self.assertEqual(delivery.payload["user_id"], str(member.user_id))
        self.assertEqual(delivery.payload["email"], "member@example.com")
        self.assertEqual(delivery.payload["role"], "admin")
        self.assertEqual(delivery.payload["removed_by_id"], str(actor.user_id))

    def test_a_change_that_rolls_back_is_never_announced(self):
        with self.assertRaises(RollbackRequested), transaction.atomic():
            create_organization_for(self.owner, {"name": "Acme"})
            raise RollbackRequested
        self.assertFalse(WebhookDelivery.objects.exists())

    @override_settings(WEBHOOKS_ENABLED=False)
    def test_nothing_is_stored_with_webhooks_off(self):
        create_organization_for(self.owner, {"name": "Acme"})
        self.assertFalse(WebhookDelivery.objects.exists())

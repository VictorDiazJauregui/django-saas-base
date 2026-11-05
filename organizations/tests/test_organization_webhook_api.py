import hashlib
import hmac
import uuid

from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from organizations.membership_changes import remove_member_as
from organizations.models import Organization
from security.models import AuditLog
from security.redaction import REDACTED_PLACEHOLDER
from security.tests.api_test_case import CacheResetAPITestCase
from security.tests.user_factory import create_user
from webhooks.delivery import deliver_due_webhooks
from webhooks.models import WebhookDelivery, WebhookEndpoint
from webhooks.tests.receiver import ReceivedRequest, RecordingReceiver

from .organization_factory import (
    add_member,
    create_member,
    create_organization,
    create_organization_api_key,
)

MEMBER_REMOVED = "organization.member_removed"
LISTED_FIELDS = {
    "id",
    "url",
    "description",
    "events",
    "is_active",
    "created_at",
    "updated_at",
}
DELIVERY_FIELDS = {
    "id",
    "event",
    "status",
    "attempts",
    "last_status_code",
    "last_error",
    "next_attempt_at",
    "delivered_at",
    "created_at",
    "payload",
}
VALID_ENDPOINT = {"url": "https://hooks.example.com/in", "events": [MEMBER_REMOVED]}


def webhooks_url(organization_reference: object) -> str:
    kwargs = {"organization_id": organization_reference}
    return reverse("organizations:webhooks", kwargs=kwargs)


def webhook_url(
    organization_reference: object, endpoint_id: object, name: str = "webhook"
) -> str:
    kwargs = {"organization_id": organization_reference, "endpoint_id": endpoint_id}
    return reverse(f"organizations:{name}", kwargs=kwargs)


def create_endpoint(organization: Organization, **fields) -> WebhookEndpoint:
    details = {**VALID_ENDPOINT, "secret": "old-secret", **fields}
    return WebhookEndpoint.objects.create(organization=organization, **details)


def is_signed_with(secret: str, received: ReceivedRequest) -> bool:
    parts = dict(
        p.split("=", 1) for p in received.headers["Webhook-Signature"].split(",")
    )
    signed = f"{parts['t']}.".encode() + received.body
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts["v1"])


@override_settings(
    TENANCY_ENABLED=True,
    WEBHOOKS_ENABLED=True,
    WEBHOOK_ALLOW_PRIVATE_URLS=True,
    WEBHOOK_ORGANIZATION_ENDPOINT_LIMIT=3,
)
class OrganizationWebhookApiTestCase(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.organization = create_organization("Acme")
        self.other = create_organization("Globex")
        self.user = create_user()

    def join(self, role: str, organization=None) -> None:
        add_member(organization or self.organization, self.user, role)
        self.client.force_authenticate(self.user)

    def create(self, payload: dict, organization_reference: object = "acme"):
        url = webhooks_url(organization_reference)
        return self.client.post(url, payload, format="json")

    def assert_error(self, response, status_code: int, code: str) -> None:
        self.assertEqual(response.status_code, status_code, response.content)
        self.assertEqual(response.json()["code"], code)

    def assert_field_error(self, response, field: str) -> None:
        self.assert_error(response, status.HTTP_400_BAD_REQUEST, "invalid")
        self.assertIn(field, response.json()["fields"])


class OrganizationWebhookCreateTests(OrganizationWebhookApiTestCase):
    def test_an_owner_gets_the_secret_once_with_the_endpoint(self):
        self.join("owner")
        response = self.create({**VALID_ENDPOINT, "description": "ERP"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertEqual(set(body), LISTED_FIELDS | {"secret"})
        endpoint = WebhookEndpoint.objects.get(pk=body["id"])
        self.assertEqual(body["secret"], endpoint.secret)
        self.assertEqual(endpoint.organization, self.organization)

    def test_an_admin_creates_by_id(self):
        self.join("admin")
        response = self.create(VALID_ENDPOINT, self.organization.pk)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_a_member_cannot_create(self):
        self.join("member")
        self.assert_error(self.create(VALID_ENDPOINT), 403, "permission_denied")
        self.assertFalse(WebhookEndpoint.objects.exists())

    def test_without_a_token_asks_for_credentials(self):
        self.assert_error(self.create(VALID_ENDPOINT), 401, "not_authenticated")

    def test_someone_from_another_organization_finds_nothing(self):
        self.join("owner", self.other)
        response = self.create(VALID_ENDPOINT)
        self.assert_error(response, 404, "organization_not_found")
        self.assertFalse(WebhookEndpoint.objects.exists())

    def test_an_organization_key_cannot_manage_webhooks(self):
        _api_key, raw_key = create_organization_api_key(self.organization, "admin")
        self.client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}")
        with self.settings(API_KEYS_ENABLED=True):
            response = self.create(VALID_ENDPOINT)
        self.assert_error(response, 403, "organization_api_key_not_allowed")

    def test_the_organization_in_the_body_is_ignored(self):
        self.join("owner")
        response = self.create({**VALID_ENDPOINT, "organization": str(self.other.pk)})
        endpoint = WebhookEndpoint.objects.get(pk=response.json()["id"])
        self.assertEqual(endpoint.organization, self.organization)

    def test_account_events_are_refused(self):
        self.join("owner")
        for event in ("user.registered", "user.email_verified"):
            response = self.create({**VALID_ENDPOINT, "events": [event]})
            self.assert_field_error(response, "events")

    def test_organization_created_is_refused(self):
        self.join("owner")
        response = self.create({**VALID_ENDPOINT, "events": ["organization.created"]})
        self.assert_field_error(response, "events")

    def test_unknown_empty_and_repeated_events_are_refused(self):
        self.join("owner")
        for events in (["invoice.paid"], [], [MEMBER_REMOVED, MEMBER_REMOVED]):
            response = self.create({**VALID_ENDPOINT, "events": events})
            self.assert_field_error(response, "events")

    @override_settings(WEBHOOK_ORGANIZATION_EVENTS=[MEMBER_REMOVED, "invoice.paid"])
    def test_a_project_event_added_to_the_catalog_is_accepted(self):
        self.join("owner")
        response = self.create({**VALID_ENDPOINT, "events": ["invoice.paid"]})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_unsafe_schemes_and_missing_hosts_are_refused(self):
        self.join("owner")
        for url in ("ftp://hooks.example.com/in", "http://"):
            self.assert_field_error(self.create({**VALID_ENDPOINT, "url": url}), "url")

    @override_settings(WEBHOOK_ALLOW_PRIVATE_URLS=False)
    def test_a_private_address_is_refused(self):
        self.join("owner")
        response = self.create({**VALID_ENDPOINT, "url": "http://127.0.0.1/hooks"})
        self.assert_field_error(response, "url")
        self.assertIn("private", response.json()["fields"]["url"][0])

    def test_the_limit_answers_conflict(self):
        self.join("owner")
        for _ in range(3):
            create_endpoint(self.organization)
        response = self.create(VALID_ENDPOINT)
        self.assert_error(response, 409, "webhook_endpoint_limit_reached")
        self.assertEqual(self.organization.webhook_endpoints.count(), 3)

    def test_the_secret_is_kept_out_of_the_audit_log(self):
        self.join("owner")
        secret = self.create(VALID_ENDPOINT).json()["secret"]
        self.assertNotIn(secret, str(AuditLog.objects.get().payload))


class OrganizationWebhookReadTests(OrganizationWebhookApiTestCase):
    def setUp(self):
        super().setUp()
        self.join("admin")
        self.endpoint = create_endpoint(self.organization)
        self.foreign = create_endpoint(self.other)

    def test_lists_only_the_endpoints_of_the_organization_without_secrets(self):
        results = self.client.get(webhooks_url("acme")).json()["results"]
        self.assertEqual([r["id"] for r in results], [str(self.endpoint.pk)])
        self.assertEqual(set(results[0]), LISTED_FIELDS)

    def test_platform_endpoints_are_not_listed(self):
        WebhookEndpoint.objects.create(secret="platform", **VALID_ENDPOINT)
        self.assertEqual(self.client.get(webhooks_url("acme")).json()["count"], 1)

    def test_reads_one_endpoint_without_its_secret(self):
        body = self.client.get(webhook_url("acme", self.endpoint.pk)).json()
        self.assertEqual(set(body), LISTED_FIELDS)

    def test_an_endpoint_of_another_organization_is_not_found(self):
        response = self.client.get(webhook_url("acme", self.foreign.pk))
        self.assert_error(response, 404, "not_found")

    def test_the_route_of_another_organization_is_not_found(self):
        response = self.client.get(webhook_url("globex", self.foreign.pk))
        self.assert_error(response, 404, "organization_not_found")

    def test_an_unknown_endpoint_is_not_found(self):
        response = self.client.get(webhook_url("acme", uuid.uuid4()))
        self.assert_error(response, 404, "not_found")

    def test_a_member_cannot_read(self):
        member = create_member(self.organization, "member@example.com")
        self.client.force_authenticate(member.user)
        response = self.client.get(webhooks_url("acme"))
        self.assert_error(response, 403, "permission_denied")


class OrganizationWebhookChangeTests(OrganizationWebhookApiTestCase):
    def setUp(self):
        super().setUp()
        self.join("admin")
        self.endpoint = create_endpoint(self.organization)
        self.foreign = create_endpoint(self.other)

    def patch(self, endpoint_id, payload: dict):
        url = webhook_url("acme", endpoint_id)
        return self.client.patch(url, payload, format="json")

    def test_edits_events_description_and_activity(self):
        payload = {"events": ["organization.member_added"], "is_active": False}
        response = self.patch(self.endpoint.pk, {**payload, "description": "CRM"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.events, ["organization.member_added"])
        self.assertFalse(self.endpoint.is_active)
        self.assertNotIn("secret", response.json())

    def test_editing_validates_url_and_events(self):
        self.assert_field_error(self.patch(self.endpoint.pk, {"url": "ftp://x"}), "url")
        response = self.patch(self.endpoint.pk, {"events": ["user.registered"]})
        self.assert_field_error(response, "events")

    def test_a_secret_in_the_body_is_ignored_and_redacted(self):
        self.patch(self.endpoint.pk, {"secret": "chosen-by-the-client"})
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.secret, "old-secret")
        self.assertEqual(AuditLog.objects.get().payload["secret"], REDACTED_PLACEHOLDER)

    def test_put_is_not_allowed(self):
        response = self.client.put(
            webhook_url("acme", self.endpoint.pk), VALID_ENDPOINT, format="json"
        )
        self.assert_error(response, 405, "method_not_allowed")

    def test_another_organization_cannot_edit_delete_or_rotate(self):
        self.assert_error(
            self.patch(self.foreign.pk, {"is_active": False}), 404, "not_found"
        )
        response = self.client.delete(webhook_url("acme", self.foreign.pk))
        self.assert_error(response, 404, "not_found")
        rotate = webhook_url("acme", self.foreign.pk, "webhook_rotate_secret")
        self.assert_error(self.client.post(rotate), 404, "not_found")
        self.foreign.refresh_from_db()
        self.assertTrue(self.foreign.is_active)
        self.assertEqual(self.foreign.secret, "old-secret")

    def test_deleting_removes_the_endpoint_and_its_deliveries(self):
        WebhookDelivery.objects.create(
            endpoint=self.endpoint, event=MEMBER_REMOVED, payload={}
        )
        response = self.client.delete(webhook_url("acme", self.endpoint.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            WebhookDelivery.objects.filter(endpoint_id=self.endpoint.pk).exists()
        )
        self.assertTrue(WebhookEndpoint.objects.filter(pk=self.foreign.pk).exists())


class OrganizationWebhookRotationTests(OrganizationWebhookApiTestCase):
    def setUp(self):
        super().setUp()
        self.join("owner")

    def test_rotating_returns_a_new_secret_once(self):
        endpoint = create_endpoint(self.organization)
        url = webhook_url("acme", endpoint.pk, "webhook_rotate_secret")
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.json()), LISTED_FIELDS | {"secret"})
        self.assertNotEqual(response.json()["secret"], "old-secret")
        self.assertNotIn(response.json()["secret"], str(AuditLog.objects.get().payload))

    def test_the_next_delivery_is_signed_with_the_new_secret(self):
        with RecordingReceiver() as receiver:
            endpoint = create_endpoint(self.organization, url=receiver.url)
            url = webhook_url("acme", endpoint.pk, "webhook_rotate_secret")
            secret = self.client.post(url).json()["secret"]
            leaver = create_member(self.organization, "leaver@example.com")
            remove_member_as(self.organization.memberships.get(user=self.user), leaver)
            deliver_due_webhooks()
        self.assertTrue(is_signed_with(secret, receiver.received[0]))
        self.assertFalse(is_signed_with("old-secret", receiver.received[0]))


class OrganizationWebhookDeliveryListTests(OrganizationWebhookApiTestCase):
    def setUp(self):
        super().setUp()
        self.join("admin")
        self.endpoint = create_endpoint(self.organization)
        self.foreign = create_endpoint(self.other)
        WebhookDelivery.objects.create(
            endpoint=self.endpoint, event=MEMBER_REMOVED, payload={"a": 1}
        )
        WebhookDelivery.objects.create(
            endpoint=self.foreign, event=MEMBER_REMOVED, payload={"b": 2}
        )

    def test_lists_the_deliveries_of_the_endpoint(self):
        url = webhook_url("acme", self.endpoint.pk, "webhook_deliveries")
        results = self.client.get(url).json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(set(results[0]), DELIVERY_FIELDS)
        self.assertEqual(results[0]["payload"], {"a": 1})

    def test_the_deliveries_of_another_organization_are_not_found(self):
        url = webhook_url("acme", self.foreign.pk, "webhook_deliveries")
        self.assert_error(self.client.get(url), 404, "not_found")

    def test_the_list_is_read_only(self):
        url = webhook_url("acme", self.endpoint.pk, "webhook_deliveries")
        self.assert_error(self.client.post(url, {}), 405, "method_not_allowed")


class OrganizationWebhookModuleOffTests(OrganizationWebhookApiTestCase):
    def setUp(self):
        super().setUp()
        self.join("owner")
        self.endpoint = create_endpoint(self.organization)

    def assert_every_route_is_missing(self) -> None:
        urls = [
            webhooks_url("acme"),
            webhook_url("acme", self.endpoint.pk),
            webhook_url("acme", self.endpoint.pk, "webhook_deliveries"),
        ]
        for url in urls:
            self.assert_error(self.client.get(url), 404, "not_found")
        rotate = webhook_url("acme", self.endpoint.pk, "webhook_rotate_secret")
        self.assert_error(self.client.post(rotate), 404, "not_found")

    @override_settings(TENANCY_ENABLED=False)
    def test_with_tenancy_off_the_routes_do_not_exist(self):
        self.assert_every_route_is_missing()

    @override_settings(WEBHOOKS_ENABLED=False)
    def test_with_webhooks_off_the_routes_do_not_exist(self):
        self.assert_every_route_is_missing()

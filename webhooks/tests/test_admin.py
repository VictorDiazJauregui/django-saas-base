from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from organizations.tests.organization_factory import create_organization
from security.models import AuditLog
from security.tests.user_factory import create_superuser, create_user
from webhooks.models import WebhookDelivery, WebhookEndpoint

ENDPOINTS_URL = "admin:webhooks_webhookendpoint_changelist"
DELIVERIES_URL = "admin:webhooks_webhookdelivery_changelist"


class WebhookAdminTestCase(TestCase):
    def setUp(self):
        self.client.force_login(create_superuser())

    def add_endpoint(self, url="https://hooks.example.com/in"):
        form_data = {
            "url": url,
            "events": "user.registered,invoice.paid",
            "is_active": "on",
        }
        return self.client.post(
            reverse("admin:webhooks_webhookendpoint_add"), form_data
        )


@override_settings(WEBHOOK_ALLOW_PRIVATE_URLS=False)
class EndpointAdminTests(WebhookAdminTestCase):
    def test_creating_an_endpoint_shows_its_secret_once(self):
        with self.settings(WEBHOOK_ALLOW_PRIVATE_URLS=True):
            response = self.add_endpoint()

        endpoint = WebhookEndpoint.objects.get()
        self.assertEqual(endpoint.events, ["user.registered", "invoice.paid"])
        self.assertContains(response, endpoint.secret)
        self.assertGreaterEqual(len(endpoint.secret), 40)
        self.assertIn("no-store", response["Cache-Control"])
        detail = self.client.get(
            reverse("admin:webhooks_webhookendpoint_change", args=[endpoint.pk])
        )
        self.assertNotContains(detail, endpoint.secret)
        self.assertNotContains(self.client.get(reverse(ENDPOINTS_URL)), endpoint.secret)

    def test_a_private_address_is_refused(self):
        response = self.add_endpoint(url="http://169.254.169.254/latest/meta-data")

        self.assertContains(response, "resolves to a private address")
        self.assertFalse(WebhookEndpoint.objects.exists())

    def test_the_audit_log_of_the_creation_has_no_secret(self):
        with self.settings(WEBHOOK_ALLOW_PRIVATE_URLS=True):
            self.add_endpoint()

        secret = WebhookEndpoint.objects.get().secret
        record = AuditLog.objects.get(
            path=reverse("admin:webhooks_webhookendpoint_add")
        )
        self.assertNotIn(secret, str(record.payload))


class DeliveryAdminTests(WebhookAdminTestCase):
    def setUp(self):
        super().setUp()
        endpoint = WebhookEndpoint.objects.create(
            url="https://hooks.example.com/in", events=["invoice.paid"], secret="s"
        )
        self.failed = WebhookDelivery.objects.create(
            endpoint=endpoint,
            event="invoice.paid",
            payload={"invoice": 7},
            status=WebhookDelivery.FAILED,
            attempts=5,
        )
        self.succeeded = WebhookDelivery.objects.create(
            endpoint=endpoint,
            event="invoice.paid",
            payload={},
            status=WebhookDelivery.SUCCEEDED,
            attempts=1,
        )

    def test_a_delivery_is_read_only(self):
        url = reverse("admin:webhooks_webhookdelivery_change", args=[self.failed.pk])

        response = self.client.get(url)

        self.assertContains(response, "&quot;invoice&quot;: 7")
        self.assertNotContains(response, 'name="_save"')
        self.assertNotContains(
            self.client.get(reverse(DELIVERIES_URL)), "Add webhook delivery"
        )

    def test_retry_now_queues_only_the_unfinished_ones(self):
        response = self.client.post(
            reverse(DELIVERIES_URL),
            {
                "action": "retry_now",
                "_selected_action": [str(self.failed.pk), str(self.succeeded.pk)],
            },
            follow=True,
        )

        self.assertContains(response, "1 delivery queued.")
        self.failed.refresh_from_db()
        self.assertEqual(self.failed.status, WebhookDelivery.PENDING)
        self.assertLessEqual(self.failed.next_attempt_at, timezone.now())

    def test_staff_without_the_permission_can_not_retry(self):
        viewer = create_user(email="viewer@example.com")
        viewer.is_staff = True
        viewer.save()
        viewer.user_permissions.add(
            Permission.objects.get(codename="view_webhookdelivery")
        )
        self.client.force_login(viewer)

        response = self.client.get(reverse(DELIVERIES_URL))

        self.assertNotContains(response, "retry_now")


@override_settings(WEBHOOK_ALLOW_PRIVATE_URLS=True)
class OrganizationEndpointAdminTests(WebhookAdminTestCase):
    def setUp(self):
        super().setUp()
        self.acme = create_organization("Acme")
        self.endpoint = WebhookEndpoint.objects.create(
            url="https://hooks.example.com/acme",
            events=["organization.member_removed"],
            secret="acme-secret",
            organization=self.acme,
        )
        self.platform = WebhookEndpoint.objects.create(
            url="https://hooks.example.com/platform",
            events=["user.registered"],
            secret="platform-secret",
        )

    def change_events(self, endpoint, events):
        form_data = {"url": endpoint.url, "events": events, "is_active": "on"}
        url = reverse("admin:webhooks_webhookendpoint_change", args=[endpoint.pk])
        return self.client.post(url, form_data)

    def test_the_list_shows_and_filters_by_organization(self):
        response = self.client.get(reverse(ENDPOINTS_URL))
        self.assertContains(response, "Acme")
        filtered = self.client.get(
            reverse(ENDPOINTS_URL), {"organization__id__exact": str(self.acme.pk)}
        )
        self.assertContains(filtered, "hooks.example.com/acme")
        self.assertNotContains(filtered, "hooks.example.com/platform")

    def test_the_list_filters_platform_endpoints(self):
        response = self.client.get(
            reverse(ENDPOINTS_URL), {"organization__isnull": "True"}
        )
        self.assertContains(response, "hooks.example.com/platform")
        self.assertNotContains(response, "hooks.example.com/acme")

    def test_the_detail_shows_the_organization_read_only(self):
        url = reverse("admin:webhooks_webhookendpoint_change", args=[self.endpoint.pk])
        response = self.client.get(url)
        self.assertContains(response, "Acme")
        self.assertNotContains(response, 'name="organization"')

    def test_an_organization_endpoint_cannot_subscribe_to_account_events(self):
        response = self.change_events(self.endpoint, "user.registered")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "user.registered")
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.events, ["organization.member_removed"])

    def test_a_platform_endpoint_still_subscribes_to_anything(self):
        response = self.change_events(self.platform, "user.registered,invoice.paid")
        self.assertEqual(response.status_code, 302)

    def test_creating_from_the_admin_makes_a_platform_endpoint(self):
        self.add_endpoint()
        created = WebhookEndpoint.objects.exclude(
            pk__in=[self.endpoint.pk, self.platform.pk]
        ).get()
        self.assertIsNone(created.organization)

    def test_the_delivery_list_shows_and_filters_by_organization(self):
        WebhookDelivery.objects.create(
            endpoint=self.endpoint, event="organization.member_removed", payload={}
        )
        WebhookDelivery.objects.create(
            endpoint=self.platform, event="user.registered", payload={}
        )
        response = self.client.get(
            reverse(DELIVERIES_URL),
            {"endpoint__organization__id__exact": str(self.acme.pk)},
        )
        self.assertContains(response, "Acme")
        self.assertContains(response, "organization.member_removed")
        self.assertNotContains(response, "hooks.example.com/platform")

    def test_an_organization_endpoint_keeps_its_allowed_events(self):
        response = self.change_events(self.endpoint, "organization.member_added")
        self.assertEqual(response.status_code, 302)
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.events, ["organization.member_added"])

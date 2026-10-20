from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

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

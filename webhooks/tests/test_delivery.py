import hashlib
import hmac
import json
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.db import transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from webhooks.delivery import (
    RETRY_DELAYS_SECONDS,
    build_body,
    claim_due_deliveries,
    deliver_due_webhooks,
)
from webhooks.destinations import UnsafeWebhookUrl, validate_destination
from webhooks.events import emit_webhook_event
from webhooks.models import WebhookDelivery, WebhookEndpoint

from .receiver import RecordingReceiver

EVENT = "invoice.paid"
SECRET = "whsec_test_secret"
NO_JITTER = mock.patch("webhooks.delivery.random.uniform", return_value=1.0)


def create_endpoint(url, events=(EVENT,), **fields):
    return WebhookEndpoint.objects.create(
        url=url, events=list(events), secret=SECRET, **fields
    )


def expected_signature(timestamp, body):
    signed = f"{timestamp}.".encode() + body
    return hmac.new(SECRET.encode(), signed, hashlib.sha256).hexdigest()


@override_settings(WEBHOOKS_ENABLED=True)
class EmitEventTests(TestCase):
    def test_creates_a_delivery_per_subscribed_active_endpoint(self):
        subscribed = create_endpoint("https://a.example.com/hooks")
        create_endpoint("https://b.example.com/hooks", events=["other.event"])
        create_endpoint("https://c.example.com/hooks", is_active=False)

        count = emit_webhook_event(EVENT, {"invoice": 7})

        self.assertEqual(count, 1)
        delivery = WebhookDelivery.objects.get()
        self.assertEqual(delivery.endpoint, subscribed)
        self.assertEqual((delivery.event, delivery.payload), (EVENT, {"invoice": 7}))
        self.assertEqual(delivery.status, WebhookDelivery.PENDING)

    @override_settings(WEBHOOKS_ENABLED=False)
    def test_does_nothing_with_the_module_off(self):
        create_endpoint("https://a.example.com/hooks")

        self.assertEqual(emit_webhook_event(EVENT, {}), 0)
        self.assertFalse(WebhookDelivery.objects.exists())

    def test_a_rolled_back_change_sends_nothing(self):
        create_endpoint("https://a.example.com/hooks")

        with self.assertRaises(RuntimeError), transaction.atomic():
            emit_webhook_event(EVENT, {})
            raise RuntimeError("the change failed")

        self.assertFalse(WebhookDelivery.objects.exists())


@override_settings(
    WEBHOOKS_ENABLED=True,
    WEBHOOK_ALLOW_PRIVATE_URLS=True,
    WEBHOOK_MAX_ATTEMPTS=3,
    WEBHOOK_TIMEOUT_SECONDS=2,
)
@NO_JITTER
class DeliveryTests(TestCase):
    def emit_to(self, receiver):
        create_endpoint(receiver.url)
        emit_webhook_event(EVENT, {"invoice": 7})
        return WebhookDelivery.objects.get()

    def test_a_2xx_marks_it_delivered_with_a_valid_signature(self, uniform):
        with RecordingReceiver(204) as receiver:
            delivery = self.emit_to(receiver)
            self.assertEqual(deliver_due_webhooks(), 1)

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.SUCCEEDED)
        self.assertEqual((delivery.attempts, delivery.last_status_code), (1, 204))
        request = receiver.received[0]
        timestamp, signature = [
            part.split("=", 1)[1]
            for part in request.headers["Webhook-Signature"].split(",")
        ]
        self.assertEqual(signature, expected_signature(timestamp, request.body))
        self.assertEqual(request.headers["Webhook-Id"], str(delivery.pk))
        self.assertEqual(request.headers["Webhook-Event"], EVENT)
        self.assertEqual(
            request.payload,
            {
                "id": str(delivery.pk),
                "event": EVENT,
                "created_at": delivery.created_at.isoformat(),
                "data": {"invoice": 7},
            },
        )

    def test_an_error_schedules_a_retry_with_backoff(self, uniform):
        with RecordingReceiver(500) as receiver:
            delivery = self.emit_to(receiver)
            before = timezone.now()
            deliver_due_webhooks()

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.PENDING)
        self.assertEqual((delivery.attempts, delivery.last_status_code), (1, 500))
        wait = (delivery.next_attempt_at - before).total_seconds()
        self.assertAlmostEqual(wait, RETRY_DELAYS_SECONDS[0], delta=5)

    def test_a_retry_is_not_sent_before_its_time(self, uniform):
        with RecordingReceiver(500) as receiver:
            self.emit_to(receiver)
            deliver_due_webhooks()

            self.assertEqual(deliver_due_webhooks(), 0)
        self.assertEqual(len(receiver.received), 1)

    def test_it_fails_after_the_last_attempt(self, uniform):
        with RecordingReceiver(500, 502, 503) as receiver:
            delivery = self.emit_to(receiver)
            for _ in range(3):
                WebhookDelivery.objects.update(next_attempt_at=timezone.now())
                deliver_due_webhooks()

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.FAILED)
        self.assertEqual((delivery.attempts, delivery.last_status_code), (3, 503))
        self.assertIsNone(delivery.delivered_at)

    def test_succeeds_on_a_later_attempt(self, uniform):
        with RecordingReceiver(500, 200) as receiver:
            delivery = self.emit_to(receiver)
            deliver_due_webhooks()
            WebhookDelivery.objects.update(next_attempt_at=timezone.now())
            deliver_due_webhooks()

        delivery.refresh_from_db()
        self.assertEqual(
            (delivery.status, delivery.attempts), (WebhookDelivery.SUCCEEDED, 2)
        )
        self.assertIsNotNone(delivery.delivered_at)

    def test_a_redirect_is_not_followed(self, uniform):
        with RecordingReceiver(
            302, location="http://169.254.169.254/latest"
        ) as receiver:
            delivery = self.emit_to(receiver)
            deliver_due_webhooks()

        delivery.refresh_from_db()
        self.assertEqual(
            (delivery.status, delivery.last_status_code), (WebhookDelivery.PENDING, 302)
        )
        self.assertEqual(len(receiver.received), 1)

    def test_a_server_that_does_not_answer_is_retried(self, uniform):
        create_endpoint("http://127.0.0.1:9/hooks")
        emit_webhook_event(EVENT, {})

        deliver_due_webhooks()

        delivery = WebhookDelivery.objects.get()
        self.assertEqual(delivery.status, WebhookDelivery.PENDING)
        self.assertIsNone(delivery.last_status_code)
        self.assertTrue(delivery.last_error)

    def test_an_inactive_endpoint_is_skipped_and_failed(self, uniform):
        with RecordingReceiver(200) as receiver:
            delivery = self.emit_to(receiver)
            WebhookEndpoint.objects.update(is_active=False)
            deliver_due_webhooks()

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.FAILED)
        self.assertEqual(receiver.received, [])

    @override_settings(WEBHOOK_ALLOW_PRIVATE_URLS=False)
    def test_a_private_address_is_not_called(self, uniform):
        with RecordingReceiver(200) as receiver:
            delivery = self.emit_to(receiver)
            deliver_due_webhooks()

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.FAILED)
        self.assertIn("private", delivery.last_error)
        self.assertEqual(receiver.received, [])


class DestinationValidationTests(TestCase):
    def assertRejected(self, url):
        with self.assertRaises(UnsafeWebhookUrl):
            validate_destination(url, allow_private=False)

    def test_internal_addresses_are_rejected(self):
        for url in (
            "http://127.0.0.1/hooks",
            "http://localhost/hooks",
            "http://10.0.0.5/hooks",
            "http://192.168.1.10/hooks",
            "http://169.254.169.254/latest/meta-data",
            "http://[::1]/hooks",
        ):
            with self.subTest(url=url):
                self.assertRejected(url)

    def test_other_schemes_and_unknown_hosts_are_rejected(self):
        for url in (
            "ftp://example.com/x",
            "file:///etc/passwd",
            "https://does-not-exist.invalid/",
        ):
            with self.subTest(url=url):
                self.assertRejected(url)

    def test_a_public_address_is_accepted(self):
        validate_destination("https://93.184.216.34/hooks", allow_private=False)

    def test_private_addresses_are_accepted_when_allowed(self):
        validate_destination("http://127.0.0.1/hooks", allow_private=True)


@override_settings(WEBHOOKS_ENABLED=True, WEBHOOK_ALLOW_PRIVATE_URLS=True)
class ConcurrentWorkersTests(TransactionTestCase):
    def test_a_claimed_delivery_is_not_taken_by_another_worker(self):
        create_endpoint("http://127.0.0.1:9/hooks")
        emit_webhook_event(EVENT, {})

        first = claim_due_deliveries(10)
        second = claim_due_deliveries(10)

        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])


@override_settings(
    WEBHOOKS_ENABLED=True, WEBHOOK_ALLOW_PRIVATE_URLS=True, WEBHOOK_TIMEOUT_SECONDS=2
)
class LeaseTests(TestCase):
    def test_the_lease_covers_the_whole_batch(self):
        create_endpoint("http://127.0.0.1:9/hooks")
        for _ in range(3):
            emit_webhook_event(EVENT, {})
        before = timezone.now()

        claimed = claim_due_deliveries(10)

        lease = (claimed[0].next_attempt_at - before).total_seconds()
        self.assertAlmostEqual(lease, 2 * (3 + 1), delta=1)
        self.assertEqual({delivery.attempts for delivery in claimed}, {1})


@override_settings(WEBHOOKS_ENABLED=True, WEBHOOK_ALLOW_PRIVATE_URLS=True)
class DeliverCommandTests(TestCase):
    def test_once_delivers_and_reports(self):
        output = StringIO()
        with RecordingReceiver(200) as receiver:
            create_endpoint(receiver.url)
            emit_webhook_event(EVENT, {})
            call_command("deliver_webhooks", "--once", stdout=output)

        self.assertEqual(len(receiver.received), 1)
        self.assertIn("Webhook deliveries processed: 1.", output.getvalue())

    def test_the_loop_stops_when_asked(self):
        with mock.patch(
            "webhooks.management.commands.deliver_webhooks.time.sleep"
        ) as sleep:
            sleep.side_effect = KeyboardInterrupt
            call_command("deliver_webhooks", "--interval", "1", stdout=StringIO())

        sleep.assert_called_once_with(1)


class PayloadTests(TestCase):
    @override_settings(WEBHOOKS_ENABLED=True)
    def test_the_payload_must_be_json(self):
        create_endpoint("https://a.example.com/hooks")

        with self.assertRaises(TypeError):
            emit_webhook_event(EVENT, {"when": object()})

    def test_the_body_is_compact_json(self):
        delivery = WebhookDelivery(
            pk=5, event=EVENT, payload={"a": 1}, created_at=timezone.now()
        )

        self.assertEqual(json.loads(build_body(delivery))["data"], {"a": 1})

from datetime import datetime, time, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from webhooks.models import WebhookDelivery, WebhookEndpoint
from webhooks.purge import build_purge_plan, delete_expired_deliveries

ONE_MICROSECOND = timedelta(microseconds=1)


def start_of_day(days_ago):
    day = timezone.localdate() - timedelta(days=days_ago)
    return timezone.make_aware(datetime.combine(day, time.min))


def create_delivery(finished_at, status=WebhookDelivery.SUCCEEDED, created_at=None):
    endpoint = WebhookEndpoint.objects.create(
        url="https://hooks.example.com/in", events=["user.registered"], secret="s"
    )
    delivery = WebhookDelivery.objects.create(
        endpoint=endpoint, event="user.registered", payload={}, status=status
    )
    WebhookDelivery.objects.filter(pk=delivery.pk).update(
        created_at=created_at or finished_at, updated_at=finished_at
    )
    return delivery


def run_purge(*arguments, answer="y"):
    output = StringIO()
    with patch("builtins.input", return_value=answer) as prompt:
        call_command("purge_webhook_deliveries", *arguments, stdout=output)
    return output.getvalue(), prompt


def remaining_ids():
    return set(WebhookDelivery.objects.values_list("pk", flat=True))


class PurgeArgumentTests(TestCase):
    def test_requires_the_period(self):
        with self.assertRaisesMessage(CommandError, "--older-than"):
            call_command("purge_webhook_deliveries")

    def test_rejects_a_period_below_one_day_or_not_a_number(self):
        for value in ("0", "-3", "abc", "1.5"):
            with self.subTest(value=value):
                with self.assertRaisesMessage(CommandError, "--older-than"):
                    call_command("purge_webhook_deliveries", "--older-than", value)


class PurgeSelectionTests(TestCase):
    def test_deletes_only_the_finished_deliveries_older_than_the_period(self):
        succeeded = create_delivery(start_of_day(40))
        failed = create_delivery(start_of_day(45), status=WebhookDelivery.FAILED)
        pending = create_delivery(start_of_day(50), status=WebhookDelivery.PENDING)
        recent = create_delivery(timezone.now())

        run_purge("--older-than", "30", "--no-input")

        self.assertEqual(remaining_ids(), {pending.pk, recent.pk})
        self.assertFalse(remaining_ids() & {succeeded.pk, failed.pk})

    def test_the_age_counts_from_when_it_finished_not_when_it_was_created(self):
        retried = create_delivery(timezone.now(), created_at=start_of_day(60))

        output, _ = run_purge("--older-than", "30", "--no-input")

        self.assertIn("No finished webhook deliveries older than 30 days", output)
        self.assertEqual(remaining_ids(), {retried.pk})

    def test_last_day_of_the_range_is_deleted_and_the_next_one_kept(self):
        last_deleted = create_delivery(start_of_day(30) - ONE_MICROSECOND)
        first_kept = create_delivery(start_of_day(30))

        run_purge("--older-than", "30", "--no-input")

        self.assertEqual(remaining_ids(), {first_kept.pk})
        self.assertNotIn(last_deleted.pk, remaining_ids())


class PurgeConfirmationTests(TestCase):
    def setUp(self):
        create_delivery(start_of_day(45))
        self.recent = create_delivery(timezone.now())

    def test_dry_run_shows_the_summary_and_deletes_nothing(self):
        output, prompt = run_purge("--older-than", "30", "--dry-run")
        first_day = timezone.localdate() - timedelta(days=45)

        self.assertIn(
            f"About to delete 1 finished webhook deliveries, from {first_day} "
            f"to {first_day} inclusive.",
            output,
        )
        self.assertIn("Dry run: nothing was deleted.", output)
        self.assertEqual(WebhookDelivery.objects.count(), 2)
        prompt.assert_not_called()

    def test_answering_no_deletes_nothing(self):
        output, _ = run_purge("--older-than", "30", answer="n")

        self.assertIn("Cancelled", output)
        self.assertEqual(WebhookDelivery.objects.count(), 2)

    def test_answering_yes_deletes_and_reports(self):
        output, _ = run_purge("--older-than", "30", answer="y")

        self.assertIn("Deleted 1 finished webhook deliveries.", output)
        self.assertEqual(remaining_ids(), {self.recent.pk})

    def test_closed_input_fails_and_suggests_no_input(self):
        with patch("builtins.input", side_effect=EOFError):
            with self.assertRaisesMessage(CommandError, "--no-input"):
                call_command(
                    "purge_webhook_deliveries",
                    "--older-than",
                    "30",
                    stdout=StringIO(),
                )

        self.assertEqual(WebhookDelivery.objects.count(), 2)


class PurgeServiceTests(TestCase):
    def test_plan_counts_the_finished_deliveries_before_the_cutoff(self):
        create_delivery(start_of_day(40))
        create_delivery(start_of_day(40), status=WebhookDelivery.PENDING)

        plan = build_purge_plan(30)

        self.assertEqual(plan.count, 1)
        self.assertEqual(plan.cutoff, start_of_day(30))

    def test_deletes_in_batches_until_nothing_is_left(self):
        for _ in range(5):
            create_delivery(start_of_day(40))

        with patch("webhooks.purge.PURGE_BATCH_SIZE", 2):
            with CaptureQueriesContext(connection) as queries:
                deleted = delete_expired_deliveries(start_of_day(30))

        deletes = [q for q in queries.captured_queries if q["sql"].startswith("DELETE")]
        self.assertEqual(deleted, 5)
        self.assertEqual(len(deletes), 3)
        self.assertFalse(WebhookDelivery.objects.exists())

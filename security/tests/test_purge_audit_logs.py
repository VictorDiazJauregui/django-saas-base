from datetime import datetime, time, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from security.audit_purge import build_purge_plan, delete_expired_records
from security.models import AuditLog

ONE_MICROSECOND = timedelta(microseconds=1)


def start_of_day(days_ago):
    day = timezone.localdate() - timedelta(days=days_ago)
    return timezone.make_aware(datetime.combine(day, time.min))


def create_entry_at(moment):
    entry = AuditLog.objects.create(method="POST", path="/purge/")
    AuditLog.objects.filter(pk=entry.pk).update(timestamp=moment)
    return entry


def run_purge(*arguments, answer="y"):
    output = StringIO()
    with patch("builtins.input", return_value=answer) as prompt:
        call_command("purge_audit_logs", *arguments, stdout=output)
    return output.getvalue(), prompt


class PurgeArgumentTests(TestCase):
    def test_requires_the_period(self):
        with self.assertRaisesMessage(CommandError, "--older-than"):
            call_command("purge_audit_logs")

    def test_rejects_a_period_below_one_day_or_not_a_number(self):
        for value in ("0", "-3", "abc", "1.5"):
            with self.subTest(value=value):
                with self.assertRaisesMessage(CommandError, "--older-than"):
                    call_command("purge_audit_logs", "--older-than", value)


class PurgeConfirmationTests(TestCase):
    def setUp(self):
        self.old_entry = create_entry_at(start_of_day(45))
        self.recent_entry = create_entry_at(timezone.now())

    def test_dry_run_shows_the_summary_and_deletes_nothing(self):
        output, prompt = run_purge("--older-than", "30", "--dry-run")

        self.assertIn("1 audit log record", output)
        self.assertEqual(AuditLog.objects.count(), 2)
        prompt.assert_not_called()

    def test_answering_no_deletes_nothing(self):
        output, _ = run_purge("--older-than", "30", answer="n")

        self.assertIn("Cancelled", output)
        self.assertEqual(AuditLog.objects.count(), 2)

    def test_answering_yes_deletes_only_the_old_records(self):
        run_purge("--older-than", "30", answer="y")

        self.assertEqual(list(AuditLog.objects.all()), [self.recent_entry])

    def test_no_input_deletes_without_asking(self):
        _, prompt = run_purge("--older-than", "30", "--no-input")

        prompt.assert_not_called()
        self.assertEqual(list(AuditLog.objects.all()), [self.recent_entry])

    def test_closed_input_fails_and_suggests_no_input(self):
        with patch("builtins.input", side_effect=EOFError):
            with self.assertRaisesMessage(CommandError, "--no-input"):
                call_command(
                    "purge_audit_logs", "--older-than", "30", stdout=StringIO()
                )

        self.assertEqual(AuditLog.objects.count(), 2)


class PurgeCutoffTests(TestCase):
    def test_last_day_of_the_range_is_deleted_and_the_next_one_kept(self):
        last_deleted = create_entry_at(start_of_day(30) - ONE_MICROSECOND)
        first_kept = create_entry_at(start_of_day(30))

        run_purge("--older-than", "30", "--no-input")

        self.assertFalse(AuditLog.objects.filter(pk=last_deleted.pk).exists())
        self.assertTrue(AuditLog.objects.filter(pk=first_kept.pk).exists())

    def test_summary_shows_the_count_and_the_inclusive_range(self):
        create_entry_at(start_of_day(45))
        create_entry_at(start_of_day(31))
        first_day = timezone.localdate() - timedelta(days=45)
        last_day = timezone.localdate() - timedelta(days=31)

        output, _ = run_purge("--older-than", "30", "--dry-run")

        self.assertIn(
            f"2 audit log records, from {first_day} to {last_day} inclusive", output
        )

    def test_without_old_records_it_says_so_and_does_not_ask(self):
        create_entry_at(timezone.now())

        output, prompt = run_purge("--older-than", "30")

        self.assertIn("No audit log records older than 30 days", output)
        prompt.assert_not_called()


class PurgeServiceTests(TestCase):
    def test_plan_counts_the_records_before_the_cutoff(self):
        create_entry_at(start_of_day(40))
        create_entry_at(start_of_day(2))

        plan = build_purge_plan(30)

        self.assertEqual(plan.count, 1)
        self.assertEqual(plan.cutoff, start_of_day(30))

    def test_deletes_in_batches_until_nothing_is_left(self):
        for _ in range(5):
            create_entry_at(start_of_day(40))

        with patch("security.audit_purge.PURGE_BATCH_SIZE", 2):
            with CaptureQueriesContext(connection) as queries:
                deleted = delete_expired_records(start_of_day(30))

        deletes = [q for q in queries.captured_queries if q["sql"].startswith("DELETE")]
        self.assertEqual(deleted, 5)
        self.assertEqual(len(deletes), 3)
        self.assertFalse(AuditLog.objects.exists())

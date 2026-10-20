from argparse import ArgumentTypeError

from django.core.management.base import BaseCommand, CommandError

CONFIRMATION_ANSWERS = frozenset({"y", "yes"})


def parse_days(raw_value):
    try:
        days = int(raw_value)
    except ValueError:
        days = 0
    if days < 1:
        raise ArgumentTypeError(f"{raw_value!r} is not a whole number of 1 or more.")
    return days


class PurgeCommand(BaseCommand):
    records_label = "records"

    def build_plan(self, older_than_days):
        raise NotImplementedError

    def delete_expired(self, cutoff):
        raise NotImplementedError

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than",
            dest="older_than_days",
            type=parse_days,
            required=True,
            metavar="DAYS",
            help="Delete records from before today minus DAYS, whole days in TIME_ZONE.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted and delete nothing.",
        )
        parser.add_argument(
            "--no-input",
            dest="interactive",
            action="store_false",
            help="Delete without asking for confirmation, for scheduled runs.",
        )

    def handle(self, *args, **options):
        days = options["older_than_days"]
        plan = self.build_plan(days)
        if not plan.count:
            self.stdout.write(f"No {self.records_label} older than {days} days.")
            return
        self.stdout.write(
            f"About to delete {plan.count} {self.records_label}, "
            f"from {plan.first_day} to {plan.last_day} inclusive."
        )
        if not self.is_deletion_approved(options):
            return
        deleted = self.delete_expired(plan.cutoff)
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {deleted} {self.records_label}.")
        )

    def is_deletion_approved(self, options):
        if options["dry_run"]:
            self.stdout.write("Dry run: nothing was deleted.")
            return False
        if options["interactive"] and not self.confirm():
            self.stdout.write("Cancelled. Nothing was deleted.")
            return False
        return True

    def confirm(self):
        try:
            answer = input("Continue? [y/N] ")
        except EOFError as error:
            raise CommandError(
                "No answer received. Run with --no-input to delete without asking."
            ) from error
        return answer.strip().lower() in CONFIRMATION_ANSWERS

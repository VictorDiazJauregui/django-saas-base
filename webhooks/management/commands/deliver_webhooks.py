import time

from django.core.management.base import BaseCommand

from webhooks.delivery import deliver_due_webhooks

DEFAULT_INTERVAL_SECONDS = 5


class Command(BaseCommand):
    help = (
        "Sends the pending webhooks. Runs until stopped, or a single batch with --once."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--once", action="store_true", help="Send one batch and exit."
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=DEFAULT_INTERVAL_SECONDS,
            help="Seconds to wait when nothing is due.",
        )

    def handle(self, *args, once, interval, **options):
        if once:
            self.deliver_batch()
            return
        try:
            self.deliver_until_stopped(interval)
        except KeyboardInterrupt:
            self.stdout.write("Stopped.")

    def deliver_until_stopped(self, interval):
        while True:
            if self.deliver_batch() == 0:
                time.sleep(interval)

    def deliver_batch(self):
        count = deliver_due_webhooks()
        self.stdout.write(f"Webhook deliveries processed: {count}.")
        return count

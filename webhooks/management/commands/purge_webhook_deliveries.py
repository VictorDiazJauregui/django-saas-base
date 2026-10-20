from core.purge_command import PurgeCommand
from webhooks.purge import build_purge_plan, delete_expired_deliveries


class Command(PurgeCommand):
    help = (
        "Delete the webhook deliveries that finished, succeeded or failed, more than the "
        "given number of days ago. Pending deliveries are never deleted."
    )
    records_label = "finished webhook deliveries"

    def build_plan(self, older_than_days):
        return build_purge_plan(older_than_days)

    def delete_expired(self, cutoff):
        return delete_expired_deliveries(cutoff)

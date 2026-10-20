from core.purge_command import PurgeCommand
from security.audit_purge import build_purge_plan, delete_expired_records


class Command(PurgeCommand):
    help = "Delete the audit log records older than the given number of days."
    records_label = "audit log records"

    def build_plan(self, older_than_days):
        return build_purge_plan(older_than_days)

    def delete_expired(self, cutoff):
        return delete_expired_records(cutoff)

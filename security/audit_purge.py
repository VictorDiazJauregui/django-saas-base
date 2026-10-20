from core.purge import PURGE_BATCH_SIZE, PurgeTarget, delete_expired, plan_purge

from .models import AuditLog

AUDIT_LOG_PURGE = PurgeTarget(records=AuditLog.objects.all, age_field="timestamp")


def build_purge_plan(older_than_days):
    return plan_purge(AUDIT_LOG_PURGE, older_than_days)


def delete_expired_records(cutoff):
    return delete_expired(AUDIT_LOG_PURGE, cutoff, PURGE_BATCH_SIZE)

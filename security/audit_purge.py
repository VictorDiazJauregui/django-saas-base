from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db.models import Count, Max, Min
from django.utils import timezone

from .models import AuditLog

# Each batch is its own DELETE and its own transaction, so writers of new records never wait
# for the whole purge.
PURGE_BATCH_SIZE = 5000


@dataclass(frozen=True)
class AuditPurgePlan:
    cutoff: datetime
    count: int
    first_day: date | None
    last_day: date | None


# Whole days in TIME_ZONE: running it twice on the same day deletes the same records, and the
# last day of the range is deleted entirely.
def build_purge_plan(older_than_days):
    cutoff = start_of_day(timezone.localdate() - timedelta(days=older_than_days))
    summary = expired_records(cutoff).aggregate(
        count=Count("id"), first=Min("timestamp"), last=Max("timestamp")
    )
    return AuditPurgePlan(
        cutoff=cutoff,
        count=summary["count"],
        first_day=local_day(summary["first"]),
        last_day=local_day(summary["last"]),
    )


def delete_expired_records(cutoff):
    deleted_total = 0
    while True:
        batch_ids = list(
            expired_records(cutoff)
            .order_by("timestamp")
            .values_list("id", flat=True)[:PURGE_BATCH_SIZE]
        )
        if not batch_ids:
            return deleted_total
        deleted_count, _ = AuditLog.objects.filter(id__in=batch_ids).delete()
        deleted_total += deleted_count


def expired_records(cutoff):
    return AuditLog.objects.filter(timestamp__lt=cutoff)


def start_of_day(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def local_day(moment):
    if moment is None:
        return None
    return timezone.localtime(moment).date()

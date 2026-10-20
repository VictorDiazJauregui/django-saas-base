from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db.models import Count, Max, Min, QuerySet
from django.utils import timezone

# Each batch is its own DELETE and its own transaction, so writers of new records never wait
# for the whole purge.
PURGE_BATCH_SIZE = 5000


@dataclass(frozen=True)
class PurgeTarget:
    records: Callable[[], QuerySet]
    age_field: str

    def expired(self, cutoff):
        return self.records().filter(**{f"{self.age_field}__lt": cutoff})


@dataclass(frozen=True)
class PurgePlan:
    cutoff: datetime
    count: int
    first_day: date | None
    last_day: date | None


# Whole days in TIME_ZONE: running it twice on the same day deletes the same records, and the
# last day of the range is deleted entirely.
def plan_purge(target, older_than_days):
    cutoff = start_of_day(timezone.localdate() - timedelta(days=older_than_days))
    summary = target.expired(cutoff).aggregate(
        count=Count("pk"), first=Min(target.age_field), last=Max(target.age_field)
    )
    return PurgePlan(
        cutoff=cutoff,
        count=summary["count"],
        first_day=local_day(summary["first"]),
        last_day=local_day(summary["last"]),
    )


def delete_expired(target, cutoff, batch_size):
    deleted_total = 0
    while True:
        batch_ids = list(
            target.expired(cutoff)
            .order_by(target.age_field)
            .values_list("pk", flat=True)[:batch_size]
        )
        if not batch_ids:
            return deleted_total
        deleted_count, _ = target.records().filter(pk__in=batch_ids).delete()
        deleted_total += deleted_count


def start_of_day(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def local_day(moment):
    if moment is None:
        return None
    return timezone.localtime(moment).date()

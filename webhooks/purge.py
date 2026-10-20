from core.purge import PURGE_BATCH_SIZE, PurgeTarget, delete_expired, plan_purge

from .models import WebhookDelivery


def finished_deliveries():
    return WebhookDelivery.objects.exclude(status=WebhookDelivery.PENDING)


# A delivery is aged from when it finished: finish() saves updated_at, and a delivery retried
# from the admin yesterday is kept even if it was created months ago. Pending ones are never
# deleted, however old: they are still to be sent.
FINISHED_DELIVERY_PURGE = PurgeTarget(
    records=finished_deliveries, age_field="updated_at"
)


def build_purge_plan(older_than_days):
    return plan_purge(FINISHED_DELIVERY_PURGE, older_than_days)


def delete_expired_deliveries(cutoff):
    return delete_expired(FINISHED_DELIVERY_PURGE, cutoff, PURGE_BATCH_SIZE)

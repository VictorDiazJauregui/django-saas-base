import hashlib
import hmac
import json
import logging
import random
import time
from datetime import timedelta
from urllib import error, request

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .destinations import UnsafeWebhookUrl, validate_destination
from .models import WebhookDelivery

logger = logging.getLogger(__name__)

RETRY_DELAYS_SECONDS = (60, 300, 1800, 7200, 43200)
JITTER_RANGE = (0.8, 1.2)
BATCH_SIZE = 20
ERROR_MAX_LENGTH = 255
USER_AGENT = "Webhooks/1.0"


# A redirect could point anywhere, the internal network included, after the destination
# was checked: a 3xx counts as a failed attempt.
class NoRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = request.build_opener(NoRedirectHandler)


def build_body(delivery):
    document = {
        "id": str(delivery.pk),
        "event": delivery.event,
        "created_at": delivery.created_at.isoformat(),
        "data": delivery.payload,
    }
    return json.dumps(document, separators=(",", ":")).encode()


# The timestamp is signed with the body, so a receiver can refuse an old request replayed.
def sign_body(secret, timestamp, body):
    signed = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()


def build_headers(delivery, body):
    timestamp = str(int(time.time()))
    signature = sign_body(delivery.endpoint.secret, timestamp, body)
    return {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "Webhook-Id": str(delivery.pk),
        "Webhook-Event": delivery.event,
        "Webhook-Signature": f"t={timestamp},v1={signature}",
    }


def post_delivery(delivery):
    body = build_body(delivery)
    # validate_destination already limited the URL to http and https.
    outgoing = request.Request(  # noqa: S310
        delivery.endpoint.url, data=body, headers=build_headers(delivery, body)
    )
    try:
        with OPENER.open(outgoing, timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as answer:
            return answer.status, ""
    except error.HTTPError as answer:
        return answer.code, f"HTTP {answer.code}"
    except OSError as failure:
        return None, str(failure)[:ERROR_MAX_LENGTH]


# The lease moves the claimed rows past the time this worker may need to send all of them, so
# other workers skip them meanwhile; if this worker dies, they become due again when it ends.
def claim_due_deliveries(limit):
    now = timezone.now()
    with transaction.atomic():
        due = WebhookDelivery.objects.select_for_update(skip_locked=True).filter(
            status=WebhookDelivery.PENDING, next_attempt_at__lte=now
        )
        claimed = list(
            due.order_by("next_attempt_at").values_list("pk", flat=True)[:limit]
        )
        lease = settings.WEBHOOK_TIMEOUT_SECONDS * (len(claimed) + 1)
        WebhookDelivery.objects.filter(pk__in=claimed).update(
            next_attempt_at=now + timedelta(seconds=lease), attempts=F("attempts") + 1
        )
    return list(
        WebhookDelivery.objects.select_related("endpoint").filter(pk__in=claimed)
    )


def finish(delivery, status, **fields):
    delivery.status = status
    for name, value in fields.items():
        setattr(delivery, name, value)
    delivery.save(update_fields=["status", *fields, "updated_at"])


def mark_failed(delivery, reason, status_code=None):
    finish(
        delivery,
        WebhookDelivery.FAILED,
        last_error=reason,
        last_status_code=status_code,
    )
    logger.warning(
        "Webhook %s to endpoint %s failed for good: %s",
        delivery.pk,
        delivery.endpoint_id,
        reason,
        extra={"event": "webhook_failed", "webhook_event": delivery.event},
    )


def retry_delay(attempts):
    base = RETRY_DELAYS_SECONDS[min(attempts, len(RETRY_DELAYS_SECONDS)) - 1]
    # Spreads the retries of many deliveries that failed together; not a secret.
    jitter = random.uniform(*JITTER_RANGE)  # noqa: S311
    return timedelta(seconds=base * jitter)


def schedule_retry(delivery, status_code, reason):
    if delivery.attempts >= settings.WEBHOOK_MAX_ATTEMPTS:
        mark_failed(delivery, reason, status_code)
        return
    next_attempt_at = timezone.now() + retry_delay(delivery.attempts)
    fields = {"last_status_code": status_code, "last_error": reason}
    finish(delivery, WebhookDelivery.PENDING, next_attempt_at=next_attempt_at, **fields)


def attempt_delivery(delivery):
    if not delivery.endpoint.is_active:
        mark_failed(delivery, "The endpoint is inactive.")
        return
    try:
        validate_destination(delivery.endpoint.url, settings.WEBHOOK_ALLOW_PRIVATE_URLS)
    except UnsafeWebhookUrl as unsafe:
        mark_failed(delivery, str(unsafe))
        return
    status_code, reason = post_delivery(delivery)
    if status_code is not None and 200 <= status_code < 300:
        finish(
            delivery,
            WebhookDelivery.SUCCEEDED,
            last_status_code=status_code,
            last_error="",
            delivered_at=timezone.now(),
        )
        return
    schedule_retry(delivery, status_code, reason)


def deliver_due_webhooks(limit=BATCH_SIZE):
    deliveries = claim_due_deliveries(limit)
    for delivery in deliveries:
        attempt_delivery(delivery)
    return len(deliveries)

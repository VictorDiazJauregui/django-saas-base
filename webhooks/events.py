from django.conf import settings

from .models import WebhookDelivery, WebhookEndpoint


# Stored in the caller's transaction: a change that rolls back never reaches the receivers,
# and one that commits is delivered even if the process stops right after.
def emit_webhook_event(event, data):
    if not settings.WEBHOOKS_ENABLED:
        return 0
    endpoints = WebhookEndpoint.objects.filter(is_active=True, events__contains=[event])
    deliveries = [
        WebhookDelivery(endpoint=endpoint, event=event, payload=data)
        for endpoint in endpoints
    ]
    return len(WebhookDelivery.objects.bulk_create(deliveries))

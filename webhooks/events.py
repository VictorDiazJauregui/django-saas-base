from django.conf import settings
from django.db.models import Q, QuerySet

from organizations.models import Organization

from .models import WebhookDelivery, WebhookEndpoint


# Stored in the caller's transaction: a change that rolls back never reaches the receivers,
# and one that commits is delivered even if the process stops right after.
def emit_webhook_event(
    event: str, data: dict, *, organization: Organization | None = None
) -> int:
    if not settings.WEBHOOKS_ENABLED:
        return 0
    deliveries = [
        WebhookDelivery(endpoint=endpoint, event=event, payload=data)
        for endpoint in find_subscribed_endpoints(event, organization)
    ]
    return len(WebhookDelivery.objects.bulk_create(deliveries))


# An organization endpoint only hears events emitted with its own organization, so an event
# without one, or of another organization, can never reach it.
def find_subscribed_endpoints(
    event: str, organization: Organization | None
) -> QuerySet[WebhookEndpoint]:
    subscribed = WebhookEndpoint.objects.filter(
        is_active=True, events__contains=[event]
    )
    platform = Q(organization__isnull=True)
    if organization is None or not settings.TENANCY_ENABLED:
        return subscribed.filter(platform)
    return subscribed.filter(platform | Q(organization=organization))

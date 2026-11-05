from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from webhooks.endpoint_secrets import generate_webhook_secret
from webhooks.models import WebhookEndpoint

from .models import Organization


class WebhookEndpointLimitReached(Exception):
    message = _("This organization has reached its limit of webhook endpoints.")


# Locking the organization row makes two simultaneous creations wait for each other, so both
# can't pass the limit with the same count.
def create_organization_webhook_endpoint(
    organization: Organization, details: dict
) -> WebhookEndpoint:
    with transaction.atomic():
        Organization.objects.select_for_update().get(pk=organization.pk)
        endpoint_count = WebhookEndpoint.objects.filter(
            organization=organization
        ).count()
        if endpoint_count >= settings.WEBHOOK_ORGANIZATION_ENDPOINT_LIMIT:
            raise WebhookEndpointLimitReached
        return WebhookEndpoint.objects.create(
            organization=organization, secret=generate_webhook_secret(), **details
        )


def rotate_webhook_endpoint_secret(endpoint: WebhookEndpoint) -> WebhookEndpoint:
    endpoint.secret = generate_webhook_secret()
    endpoint.save(update_fields=["secret", "updated_at"])
    return endpoint

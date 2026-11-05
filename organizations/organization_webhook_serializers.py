from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from webhooks.destinations import UnsafeWebhookUrl, validate_destination
from webhooks.models import WebhookDelivery, WebhookEndpoint
from webhooks.subscriptions import (
    OrganizationEventNotAllowed,
    ensure_organization_events,
)


class OrganizationWebhookEndpointSerializer(serializers.ModelSerializer):
    events = serializers.ListField(
        child=serializers.CharField(max_length=100), allow_empty=False
    )

    class Meta:
        model = WebhookEndpoint
        fields = [
            "id",
            "url",
            "description",
            "events",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_url(self, value: str) -> str:
        try:
            validate_destination(value, settings.WEBHOOK_ALLOW_PRIVATE_URLS)
        except UnsafeWebhookUrl as unsafe:
            raise serializers.ValidationError(str(unsafe)) from unsafe
        return value

    def validate_events(self, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise serializers.ValidationError(_("Each event can be listed only once."))
        try:
            ensure_organization_events(value)
        except OrganizationEventNotAllowed as refused:
            raise serializers.ValidationError(str(refused)) from refused
        return value


# The secret travels only in the answers to the creation and the rotation.
class CreatedOrganizationWebhookEndpointSerializer(
    OrganizationWebhookEndpointSerializer
):
    secret = serializers.CharField(read_only=True)

    class Meta(OrganizationWebhookEndpointSerializer.Meta):
        fields = [*OrganizationWebhookEndpointSerializer.Meta.fields, "secret"]


class OrganizationWebhookDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookDelivery
        fields = [
            "id",
            "event",
            "status",
            "attempts",
            "last_status_code",
            "last_error",
            "next_attempt_at",
            "delivered_at",
            "created_at",
            "payload",
        ]
        read_only_fields = fields

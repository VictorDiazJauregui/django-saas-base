from django import forms
from django.conf import settings

from .destinations import UnsafeWebhookUrl, validate_destination
from .models import WebhookEndpoint
from .subscriptions import OrganizationEventNotAllowed, ensure_organization_events


class WebhookEndpointForm(forms.ModelForm):
    class Meta:
        model = WebhookEndpoint
        fields = ("url", "description", "events", "is_active")

    def clean_url(self):
        url = self.cleaned_data["url"]
        try:
            validate_destination(url, settings.WEBHOOK_ALLOW_PRIVATE_URLS)
        except UnsafeWebhookUrl as unsafe:
            raise forms.ValidationError(str(unsafe)) from unsafe
        return url

    # Staff can edit an endpoint of an organization here too: the same events as by the API.
    def clean_events(self) -> list[str]:
        events = self.cleaned_data["events"]
        if self.instance.organization_id is None:
            return events
        try:
            ensure_organization_events(events)
        except OrganizationEventNotAllowed as refused:
            raise forms.ValidationError(str(refused)) from refused
        return events

from django import forms
from django.conf import settings

from .destinations import UnsafeWebhookUrl, validate_destination
from .models import WebhookEndpoint


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

import json
import secrets

from django.contrib import admin, messages
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from .forms import WebhookEndpointForm
from .models import WebhookDelivery, WebhookEndpoint

SECRET_BYTES = 32
ENDPOINT_CREATED_TEMPLATE = "admin/webhooks/webhookendpoint/created.html"
DELIVERY_FIELDS = (
    "event",
    "endpoint",
    "status",
    "attempts",
    "last_status_code",
    "last_error",
    "next_attempt_at",
    "delivered_at",
    "created_at",
)


# The secret signs every delivery, so it stays in the database, but the admin shows it only
# in the page that answers the creation.
@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    form = WebhookEndpointForm
    list_display = ("url", "event_list", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("url", "description")

    @admin.display(description=_("events"))
    def event_list(self, obj):
        return ", ".join(obj.events)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.secret = secrets.token_urlsafe(SECRET_BYTES)
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "endpoint": obj,
        }
        response = TemplateResponse(request, ENDPOINT_CREATED_TEMPLATE, context)
        add_never_cache_headers(response)
        return response


# A delivery record is history: it is read and retried, never edited.
@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "event",
        "endpoint",
        "status",
        "attempts",
        "last_status_code",
        "next_attempt_at",
    )
    list_filter = ("status",)
    list_select_related = ("endpoint",)
    search_fields = ("event", "endpoint__url")
    fields = (*DELIVERY_FIELDS, "pretty_payload")
    readonly_fields = fields
    actions = ("retry_now",)
    show_full_result_count = False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_retry_permission(self, request):
        return request.user.has_perm("webhooks.change_webhookdelivery")

    @admin.display(description=_("payload"))
    def pretty_payload(self, obj):
        formatted = json.dumps(obj.payload, indent=2, ensure_ascii=False)
        return format_html("<pre style='white-space: pre-wrap;'>{}</pre>", formatted)

    # A failed delivery gets one more attempt; a pending one stops waiting for its backoff.
    @admin.action(description=_("Retry now"), permissions=["retry"])
    def retry_now(self, request, queryset):
        count = queryset.exclude(status=WebhookDelivery.SUCCEEDED).update(
            status=WebhookDelivery.PENDING, next_attempt_at=timezone.now()
        )
        message = ngettext(
            "%(count)d delivery queued.", "%(count)d deliveries queued.", count
        )
        self.message_user(request, message % {"count": count}, messages.SUCCESS)

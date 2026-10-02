import json

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .forms import EmailUserChangeForm, EmailUserCreationForm
from .models import AuditLog

User = get_user_model()

EMPTY_PAYLOAD_LABEL = "-"
SHORT_PAYLOAD_MAX_LENGTH = 75
TRUNCATION_SUFFIX = "..."
PERMISSION_FIELDS = (
    "is_active",
    "is_staff",
    "is_superuser",
    "groups",
    "user_permissions",
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = EmailUserChangeForm
    add_form = EmailUserCreationForm
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name")}),
        (_("Permissions"), {"fields": PERMISSION_FIELDS}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "usable_password", "password1", "password2"),
            },
        ),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "user",
        "method",
        "path",
        "ip_address",
        "short_payload",
    )
    list_filter = ("method", "user", "timestamp")
    search_fields = (
        "user__email",
        "path",
        "method",
        "ip_address",
        "user_agent",
        "payload",
    )
    readonly_fields = (
        "user",
        "ip_address",
        "user_agent",
        "method",
        "path",
        "pretty_payload",
        "timestamp",
    )
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)
    list_per_page = 25

    fields = (
        "timestamp",
        "user",
        "ip_address",
        "user_agent",
        "method",
        "path",
        "pretty_payload",
    )

    @admin.display(description="Payload")
    def short_payload(self, obj):
        if not obj.payload:
            return EMPTY_PAYLOAD_LABEL
        serialized_payload = json.dumps(obj.payload, ensure_ascii=False)
        if len(serialized_payload) <= SHORT_PAYLOAD_MAX_LENGTH:
            return serialized_payload
        visible_length = SHORT_PAYLOAD_MAX_LENGTH - len(TRUNCATION_SUFFIX)
        return serialized_payload[:visible_length] + TRUNCATION_SUFFIX

    @admin.display(description="Payload (formatted)")
    def pretty_payload(self, obj):
        if not obj.payload:
            return EMPTY_PAYLOAD_LABEL
        formatted_payload = json.dumps(obj.payload, indent=2, ensure_ascii=False)
        return format_html(
            "<pre style='white-space: pre-wrap;'>{}</pre>", formatted_payload
        )

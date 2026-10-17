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
NO_STATUS = "none"
STATUS_CLASS_RANGES = {
    "2xx": (200, 299),
    "3xx": (300, 399),
    "4xx": (400, 499),
    "5xx": (500, 599),
}
PERMISSION_FIELDS = (
    "is_active",
    "is_email_verified",
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
    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "is_email_verified",
    )
    list_filter = (*BaseUserAdmin.list_filter, "is_email_verified")
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


# A filter on the exact code would run a SELECT DISTINCT over the whole table on every page
# load; status classes are a fixed list and answer the usual question: what failed.
class StatusClassListFilter(admin.SimpleListFilter):
    title = _("status")
    parameter_name = "status_class"

    def lookups(self, request, model_admin):
        status_classes = [(name, name) for name in STATUS_CLASS_RANGES]
        return [*status_classes, (NO_STATUS, _("No status"))]

    def queryset(self, request, queryset):
        if self.value() == NO_STATUS:
            return queryset.filter(status_code__isnull=True)
        status_range = STATUS_CLASS_RANGES.get(self.value())
        if status_range is None:
            return queryset
        return queryset.filter(status_code__range=status_range)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "user",
        "method",
        "path",
        "status_code",
        "ip_address",
        "short_payload",
    )
    list_filter = ("method", StatusClassListFilter, "timestamp")
    list_select_related = ("user",)
    show_full_result_count = False
    search_fields = (
        "user__email",
        "path",
        "method",
        "ip_address",
        "user_agent",
    )
    readonly_fields = (
        "user",
        "ip_address",
        "user_agent",
        "method",
        "path",
        "status_code",
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
        "status_code",
        "pretty_payload",
    )

    # An audit trail that admins can edit proves nothing, so not even superusers can
    # add, change or delete records here.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Payload"))
    def short_payload(self, obj):
        if not obj.payload:
            return EMPTY_PAYLOAD_LABEL
        serialized_payload = json.dumps(obj.payload, ensure_ascii=False)
        if len(serialized_payload) <= SHORT_PAYLOAD_MAX_LENGTH:
            return serialized_payload
        visible_length = SHORT_PAYLOAD_MAX_LENGTH - len(TRUNCATION_SUFFIX)
        return serialized_payload[:visible_length] + TRUNCATION_SUFFIX

    @admin.display(description=_("Payload (formatted)"))
    def pretty_payload(self, obj):
        if not obj.payload:
            return EMPTY_PAYLOAD_LABEL
        formatted_payload = json.dumps(obj.payload, indent=2, ensure_ascii=False)
        return format_html(
            "<pre style='white-space: pre-wrap;'>{}</pre>", formatted_payload
        )

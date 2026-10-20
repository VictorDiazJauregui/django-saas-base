import json

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Exists, OuterRef
from django.template.response import TemplateResponse
from django.utils.cache import add_never_cache_headers
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from .api_keys import assign_new_key, revoke_api_keys
from .forms import (
    EmailUserChangeForm,
    EmailUserCreationForm,
    TwoFactorAdminAuthenticationForm,
)
from .middleware import AUDITED_METHODS
from .models import ApiKey, AuditLog, ExternalIdentity, TotpDevice
from .security_events import log_two_factor_changed
from .two_factor import disable_totp_for

User = get_user_model()

admin.site.login_form = TwoFactorAdminAuthenticationForm
admin.site.login_template = "security/admin_login.html"

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


# Read only: a link is created by logging in with the provider and removed with the user.
class ExternalIdentityInline(admin.TabularInline):
    model = ExternalIdentity
    fields = ("provider", "subject", "created_at")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


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
        "has_two_factor",
    )
    list_filter = (*BaseUserAdmin.list_filter, "is_email_verified")
    actions = ("turn_off_two_factor",)
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

    # Only on an existing user: the add form has no links to show.
    def get_inlines(self, request, obj):
        return (ExternalIdentityInline,) if obj is not None else ()

    # One subquery for the whole page instead of a query per row.
    def get_queryset(self, request):
        confirmed = TotpDevice.objects.filter(
            user=OuterRef("pk"), confirmed_at__isnull=False
        )
        return super().get_queryset(request).annotate(two_factor=Exists(confirmed))

    @admin.display(description=_("Two-factor"), boolean=True, ordering="two_factor")
    def has_two_factor(self, obj):
        return obj.two_factor

    # For a user who lost the phone and the recovery codes: the next login asks only for the
    # password, and the user can turn it on again.
    @admin.action(
        description=_("Turn off two-factor authentication"), permissions=["change"]
    )
    def turn_off_two_factor(self, request, queryset):
        users = list(queryset.filter(two_factor=True))
        disable_totp_for(users)
        for user in users:
            log_two_factor_changed(user, enabled=False)
        message = ngettext(
            "Two-factor authentication turned off for %(count)d user.",
            "Two-factor authentication turned off for %(count)d users.",
            len(users),
        )
        self.message_user(request, message % {"count": len(users)}, messages.SUCCESS)


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


# Only the audited methods can be stored, so the options are fixed instead of read with a
# SELECT DISTINCT over the whole table on every page load.
class AuditedMethodListFilter(admin.SimpleListFilter):
    title = AuditLog._meta.get_field("method").verbose_name
    parameter_name = "method"

    def lookups(self, request, model_admin):
        return [(method, method) for method in sorted(AUDITED_METHODS)]

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        return queryset.filter(method=self.value())


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
    # No date_hierarchy: its year/month/day bar runs a SELECT DISTINCT over the whole table on
    # every load. The timestamp filter covers the usual ranges without reading the table.
    list_filter = (AuditedMethodListFilter, StatusClassListFilter, "timestamp")
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


API_KEY_ADD_FIELDS = ("user", "name", "expires_at")
API_KEY_DETAIL_FIELDS = (
    "name",
    "user",
    "prefix",
    "created_at",
    "last_used_at",
    "expires_at",
    "revoked_at",
)
API_KEY_CREATED_TEMPLATE = "admin/security/apikey/created.html"


# A key is never edited: it is created, used and revoked. The secret exists only in the page
# that answers the creation, so it never reaches the database, the session or a cookie.
@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "prefix", "last_used_at", "revoked_at")
    list_select_related = ("user",)
    list_filter = ("created_at", "revoked_at")
    search_fields = ("name", "prefix", "user__email")
    autocomplete_fields = ("user",)
    actions = ("revoke_selected",)

    def get_fields(self, request, obj=None):
        return API_KEY_ADD_FIELDS if obj is None else API_KEY_DETAIL_FIELDS

    def get_readonly_fields(self, request, obj=None):
        return () if obj is None else API_KEY_DETAIL_FIELDS

    def has_change_permission(self, request, obj=None):
        return False

    def has_revoke_permission(self, request):
        opts = self.opts
        return request.user.has_perm(f"{opts.app_label}.change_{opts.model_name}")

    def save_model(self, request, obj, form, change):
        request.new_api_key = assign_new_key(obj)
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "api_key": obj,
            "raw_key": request.new_api_key,
        }
        response = TemplateResponse(request, API_KEY_CREATED_TEMPLATE, context)
        add_never_cache_headers(response)
        return response

    @admin.action(description=_("Revoke selected API keys"), permissions=["revoke"])
    def revoke_selected(self, request, queryset):
        count = revoke_api_keys(queryset)
        message = ngettext(
            "%(count)d API key revoked.", "%(count)d API keys revoked.", count
        )
        self.message_user(request, message % {"count": count}, messages.SUCCESS)

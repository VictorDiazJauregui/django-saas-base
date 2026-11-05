from django.contrib import admin, messages
from django.db.models import Count, QuerySet
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.utils.cache import add_never_cache_headers
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from security.api_keys import assign_new_key

from .invitations import revoke_invitations
from .models import Invitation, Membership, Organization, OrganizationApiKey
from .organization_api_keys import (
    ORGANIZATION_API_KEY_MARKER,
    revoke_organization_api_keys,
)


class OrganizationMembershipInline(admin.TabularInline):
    model = Membership
    fields = ("user", "role", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("user",)
    extra = 0


# Read only on the user page: memberships are managed from the organization they belong to.
class UserMembershipInline(admin.TabularInline):
    model = Membership
    fields = ("organization", "role", "created_at")
    readonly_fields = fields
    extra = 0
    can_delete = False
    verbose_name_plural = _("organizations")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "member_count", "created_at")
    search_fields = ("name", "slug")
    readonly_fields = ("id", "created_at", "updated_at")
    fields = ("id", "name", "slug", "created_at", "updated_at")
    inlines = (OrganizationMembershipInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(member_count=Count("memberships"))

    @admin.display(description=_("members"), ordering="member_count")
    def member_count(self, obj):
        return obj.member_count


# Created from the API, which emails the link; the admin lists them and revokes them.
@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "organization", "role", "status_label", "expires_at")
    list_filter = ("role",)
    search_fields = ("email", "organization__name")
    list_select_related = ("organization",)
    fields = (
        "email",
        "organization",
        "role",
        "invited_by",
        "expires_at",
        "accepted_at",
        "revoked_at",
        "created_at",
    )
    readonly_fields = fields
    actions = ("revoke_invitations",)

    def has_add_permission(self, request):
        return False

    @admin.display(description=_("status"))
    def status_label(self, obj):
        return Invitation.STATUS_LABELS[obj.status]

    @admin.action(description=_("Revoke selected invitations"), permissions=["change"])
    def revoke_invitations(self, request, queryset):
        count = revoke_invitations(queryset)
        message = ngettext(
            "%(count)d invitation revoked.", "%(count)d invitations revoked.", count
        )
        self.message_user(request, message % {"count": count}, messages.SUCCESS)


ORGANIZATION_API_KEY_ADD_FIELDS = ("organization", "name", "role", "expires_at")
ORGANIZATION_API_KEY_DETAIL_FIELDS = (
    "organization",
    "name",
    "prefix",
    "role",
    "created_by",
    "created_at",
    "last_used_at",
    "expires_at",
    "revoked_at",
)
ORGANIZATION_API_KEY_CREATED_TEMPLATE = (
    "admin/organizations/organizationapikey/created.html"
)


# Same flow as the personal keys: created, used and revoked, never edited. The key exists only
# in the page that answers the creation, so it never reaches the database, the session or a cookie.
@admin.register(OrganizationApiKey)
class OrganizationApiKeyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "prefix",
        "role",
        "last_used_at",
        "revoked_at",
    )
    list_select_related = ("organization",)
    list_filter = ("role", "created_at", "revoked_at")
    search_fields = ("prefix", "name", "organization__name", "organization__slug")
    autocomplete_fields = ("organization",)
    actions = ("revoke_selected",)

    def get_fields(self, request: HttpRequest, obj: OrganizationApiKey | None = None):
        if obj is None:
            return ORGANIZATION_API_KEY_ADD_FIELDS
        return ORGANIZATION_API_KEY_DETAIL_FIELDS

    def get_readonly_fields(
        self, request: HttpRequest, obj: OrganizationApiKey | None = None
    ):
        return () if obj is None else ORGANIZATION_API_KEY_DETAIL_FIELDS

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    def has_revoke_permission(self, request: HttpRequest) -> bool:
        opts = self.opts
        return request.user.has_perm(f"{opts.app_label}.change_{opts.model_name}")

    def save_model(self, request, obj, form, change) -> None:
        obj.created_by = request.user
        request.new_api_key = assign_new_key(obj, ORGANIZATION_API_KEY_MARKER)
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None) -> HttpResponse:
        context = {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "api_key": obj,
            "raw_key": request.new_api_key,
        }
        response = TemplateResponse(
            request, ORGANIZATION_API_KEY_CREATED_TEMPLATE, context
        )
        add_never_cache_headers(response)
        return response

    @admin.action(description=_("Revoke selected API keys"), permissions=["revoke"])
    def revoke_selected(
        self, request: HttpRequest, queryset: QuerySet[OrganizationApiKey]
    ) -> None:
        count = revoke_organization_api_keys(queryset)
        message = ngettext(
            "%(count)d API key revoked.", "%(count)d API keys revoked.", count
        )
        self.message_user(request, message % {"count": count}, messages.SUCCESS)

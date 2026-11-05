from django.contrib import admin
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from .models import Membership, Organization


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

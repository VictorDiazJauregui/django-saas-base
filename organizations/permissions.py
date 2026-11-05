from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import NotFound

from security.permissions import ConfiguredPermission

from .active_organization import resolve_active_membership
from .roles import OrganizationRole, role_includes


class HasOrganizationRole(ConfiguredPermission):
    def __init__(self, role):
        if role not in OrganizationRole.values:
            raise ImproperlyConfigured(
                f"HasOrganizationRole({role!r}) needs one of: "
                f"{', '.join(OrganizationRole.values)}."
            )
        self.role = role

    # With the module off the routes don't exist, as before it was added.
    def has_permission(self, request, view):
        if not settings.TENANCY_ENABLED:
            raise NotFound
        if not request.user.is_authenticated:
            return False
        membership = resolve_active_membership(request, view)
        return role_includes(membership.role, self.role)


class IsOrganizationMember(HasOrganizationRole):
    def __init__(self):
        super().__init__(OrganizationRole.MEMBER)

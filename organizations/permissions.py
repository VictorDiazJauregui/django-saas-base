from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.views import APIView

from security.permissions import ConfiguredPermission

from .active_organization import (
    find_request_organization_api_key,
    resolve_active_organization,
)
from .roles import OrganizationRole, role_includes


class HasOrganizationRole(ConfiguredPermission):
    def __init__(self, role: str) -> None:
        if role not in OrganizationRole.values:
            raise ImproperlyConfigured(
                f"HasOrganizationRole({role!r}) needs one of: "
                f"{', '.join(OrganizationRole.values)}."
            )
        self.role = role

    # With the module off the routes don't exist, as before it was added.
    def has_permission(self, request: Request, view: APIView) -> bool:
        if not settings.TENANCY_ENABLED:
            raise NotFound
        if not is_organization_actor(request):
            return False
        resolve_active_organization(request, view)
        return role_includes(request.organization_role, self.role)


class IsOrganizationMember(HasOrganizationRole):
    def __init__(self) -> None:
        super().__init__(OrganizationRole.MEMBER)


def is_organization_actor(request: Request) -> bool:
    if request.user.is_authenticated:
        return True
    return find_request_organization_api_key(request) is not None

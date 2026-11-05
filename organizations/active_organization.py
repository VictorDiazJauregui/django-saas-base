from django.contrib.auth.base_user import AbstractBaseUser
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.views import APIView

from .models import Membership, Organization, OrganizationApiKey
from .organization_ids import parse_organization_id

ORGANIZATION_URL_KWARG = "organization_id"


# One answer for a missing organization and for someone else's: a different one would tell
# any user which organization ids exist.
class OrganizationNotFound(NotFound):
    default_detail = _("Organization not found.")
    default_code = "organization_not_found"


def find_request_organization_api_key(request: Request) -> OrganizationApiKey | None:
    api_key = request.auth
    return api_key if isinstance(api_key, OrganizationApiKey) else None


def resolve_active_organization(request: Request, view: APIView) -> Organization:
    cached_organization = getattr(request, "organization", None)
    if cached_organization is not None:
        return cached_organization
    api_key = find_request_organization_api_key(request)
    if api_key is None:
        return resolve_active_membership(request, view).organization
    if not key_belongs_to(api_key, view.kwargs.get(ORGANIZATION_URL_KWARG)):
        raise OrganizationNotFound
    request.membership = None
    request.organization = api_key.organization
    request.organization_role = api_key.role
    return api_key.organization


def resolve_active_membership(request: Request, view: APIView) -> Membership:
    cached_membership = getattr(request, "membership", None)
    if cached_membership is not None:
        return cached_membership
    membership = find_membership(request.user, view.kwargs.get(ORGANIZATION_URL_KWARG))
    if membership is None:
        raise OrganizationNotFound
    request.membership = membership
    request.organization = membership.organization
    request.organization_role = membership.role
    return membership


def key_belongs_to(api_key: OrganizationApiKey, organization_reference: object) -> bool:
    organization_id = parse_organization_id(organization_reference)
    if organization_id is not None:
        return organization_id == api_key.organization_id
    return str(organization_reference) == api_key.organization.slug


def find_membership(
    user: AbstractBaseUser, organization_reference: object
) -> Membership | None:
    organization_filter = build_organization_filter(
        organization_reference, "organization__"
    )
    memberships = Membership.objects.select_related("organization")
    return memberships.filter(organization_filter, user=user).first()


# Slugs can never look like a UUID, so a value that parses as one is always an id.
def build_organization_filter(organization_reference: object, prefix: str = "") -> Q:
    organization_id = parse_organization_id(organization_reference)
    if organization_id is not None:
        return Q(**{f"{prefix}id": organization_id})
    return Q(**{f"{prefix}slug": str(organization_reference)})

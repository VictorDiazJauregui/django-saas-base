import uuid

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import NotFound

from .models import Membership

ORGANIZATION_URL_KWARG = "organization_id"


# One answer for a missing organization and for someone else's: a different one would tell
# any user which organization ids exist.
class OrganizationNotFound(NotFound):
    default_detail = _("Organization not found.")
    default_code = "organization_not_found"


def resolve_active_membership(request, view):
    cached_membership = getattr(request, "membership", None)
    if cached_membership is not None:
        return cached_membership
    membership = find_membership(request.user, view.kwargs.get(ORGANIZATION_URL_KWARG))
    if membership is None:
        raise OrganizationNotFound
    request.membership = membership
    request.organization = membership.organization
    return membership


def find_membership(user, raw_organization_id):
    organization_id = parse_organization_id(raw_organization_id)
    if organization_id is None:
        return None
    memberships = Membership.objects.select_related("organization")
    return memberships.filter(user=user, organization_id=organization_id).first()


def parse_organization_id(raw_organization_id):
    try:
        return uuid.UUID(str(raw_organization_id))
    except ValueError:
        return None

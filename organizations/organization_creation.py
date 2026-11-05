from django.db import IntegrityError, transaction

from .models import Membership, Organization
from .organization_events import emit_organization_created
from .roles import OrganizationRole

SLUG_ATTEMPTS = 3


# Two requests with the same name can pick the same free slug at once; the one that loses the
# race takes the next free slug instead of failing. A slug the user chose is never changed.
def create_organization_for(owner, details):
    attempts_left = SLUG_ATTEMPTS
    while True:
        try:
            return create_with_owner(owner, details)
        except IntegrityError:
            attempts_left -= 1
            if details.get("slug") or not attempts_left:
                raise


def create_with_owner(owner, details):
    with transaction.atomic():
        organization = Organization.objects.create(**details)
        Membership.objects.create(
            organization=organization, user=owner, role=OrganizationRole.OWNER
        )
        emit_organization_created(organization, owner)
    return organization

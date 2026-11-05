from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .models import Membership
from .roles import OrganizationRole


class LastOwnerError(Exception):
    message = _("An organization needs at least one owner.")


def change_member_role(membership, role):
    with transaction.atomic():
        if role != OrganizationRole.OWNER:
            ensure_another_owner_remains(membership)
        membership.role = role
        membership.save(update_fields=["role", "updated_at"])
    return membership


def remove_member(membership):
    with transaction.atomic():
        ensure_another_owner_remains(membership)
        membership.delete()


# Locking every owner row serializes concurrent changes: two owners removing each other at
# the same time can't both see the other one still there.
def ensure_another_owner_remains(membership):
    owners = Membership.objects.select_for_update().filter(
        organization_id=membership.organization_id, role=OrganizationRole.OWNER
    )
    owner_ids = set(owners.values_list("pk", flat=True))
    if owner_ids == {membership.pk}:
        raise LastOwnerError(LastOwnerError.message)

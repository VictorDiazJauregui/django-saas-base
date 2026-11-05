from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .models import Membership
from .organization_events import emit_member_removed
from .roles import OrganizationRole, role_includes


class LastOwnerError(Exception):
    message = _("An organization needs at least one owner.")


class MembershipChangeDenied(Exception):
    pass


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


def change_member_role_as(actor, membership, role):
    ensure_actor_manages(actor, membership, role)
    return change_member_role(membership, role)


def remove_member_as(actor, membership):
    if actor.pk != membership.pk:
        ensure_actor_manages(actor, membership, membership.role)
    with transaction.atomic():
        remove_member(membership)
        emit_member_removed(membership, actor.user)


def ensure_actor_manages(actor, membership, new_role):
    ensure_actor_grants(actor, membership.role)
    ensure_actor_grants(actor, new_role)


# Admins manage members and admins; only an owner touches the owner role, given or taken.
def ensure_actor_grants(actor, role):
    if not role_includes(actor.role, OrganizationRole.ADMIN):
        raise MembershipChangeDenied
    if role == OrganizationRole.OWNER and actor.role != OrganizationRole.OWNER:
        raise MembershipChangeDenied


# Locking every owner row serializes concurrent changes: two owners removing each other at
# the same time can't both see the other one still there.
def ensure_another_owner_remains(membership):
    owners = Membership.objects.select_for_update().filter(
        organization_id=membership.organization_id, role=OrganizationRole.OWNER
    )
    owner_ids = set(owners.values_list("pk", flat=True))
    if owner_ids == {membership.pk}:
        raise LastOwnerError(LastOwnerError.message)

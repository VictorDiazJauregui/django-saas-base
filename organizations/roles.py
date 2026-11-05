from django.db import models
from django.utils.translation import gettext_lazy as _


class OrganizationRole(models.TextChoices):
    OWNER = "owner", _("Owner")
    ADMIN = "admin", _("Admin")
    MEMBER = "member", _("Member")


ROLE_RANKS = {
    OrganizationRole.MEMBER: 1,
    OrganizationRole.ADMIN: 2,
    OrganizationRole.OWNER: 3,
}


def role_includes(held_role, required_role):
    return ROLE_RANKS[held_role] >= ROLE_RANKS[required_role]


# An organization key never owns the organization: owners are people who can be held to account.
ORGANIZATION_API_KEY_ROLES = [
    (OrganizationRole.ADMIN.value, OrganizationRole.ADMIN.label),
    (OrganizationRole.MEMBER.value, OrganizationRole.MEMBER.label),
]

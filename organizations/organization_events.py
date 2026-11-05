from django.contrib.auth.base_user import AbstractBaseUser

from webhooks.events import emit_webhook_event

from .models import Membership, Organization

ORGANIZATION_CREATED = "organization.created"
ORGANIZATION_MEMBER_ADDED = "organization.member_added"
ORGANIZATION_MEMBER_REMOVED = "organization.member_removed"


def emit_organization_created(
    organization: Organization, owner: AbstractBaseUser
) -> None:
    emit_webhook_event(
        ORGANIZATION_CREATED,
        {
            "organization_id": str(organization.pk),
            "name": organization.name,
            "slug": organization.slug,
            "owner_id": str(owner.pk),
            "owner_email": owner.email,
        },
        organization=organization,
    )


def emit_member_added(membership: Membership) -> None:
    emit_webhook_event(
        ORGANIZATION_MEMBER_ADDED,
        describe_membership(membership),
        organization=membership.organization,
    )


def emit_member_removed(membership: Membership, removed_by: AbstractBaseUser) -> None:
    payload = {**describe_membership(membership), "removed_by_id": str(removed_by.pk)}
    emit_webhook_event(
        ORGANIZATION_MEMBER_REMOVED, payload, organization=membership.organization
    )


def describe_membership(membership: Membership) -> dict:
    return {
        "organization_id": str(membership.organization_id),
        "user_id": str(membership.user_id),
        "email": membership.user.email,
        "role": membership.role,
    }

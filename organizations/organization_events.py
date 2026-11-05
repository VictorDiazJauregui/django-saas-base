from webhooks.events import emit_webhook_event

ORGANIZATION_CREATED = "organization.created"
ORGANIZATION_MEMBER_ADDED = "organization.member_added"
ORGANIZATION_MEMBER_REMOVED = "organization.member_removed"


def emit_organization_created(organization, owner):
    emit_webhook_event(
        ORGANIZATION_CREATED,
        {
            "organization_id": str(organization.pk),
            "name": organization.name,
            "slug": organization.slug,
            "owner_id": str(owner.pk),
            "owner_email": owner.email,
        },
    )


def emit_member_added(membership):
    emit_webhook_event(ORGANIZATION_MEMBER_ADDED, describe_membership(membership))


def emit_member_removed(membership, removed_by):
    payload = {**describe_membership(membership), "removed_by_id": str(removed_by.pk)}
    emit_webhook_event(ORGANIZATION_MEMBER_REMOVED, payload)


def describe_membership(membership):
    return {
        "organization_id": str(membership.organization_id),
        "user_id": str(membership.user_id),
        "email": membership.user.email,
        "role": membership.role,
    }

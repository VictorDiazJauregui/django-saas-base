import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from core.emails import send_templated_email
from security.account_events import USER_REGISTERED, emit_account_event
from security.google_login import AccountExists
from security.serializers import validate_password_for_new_user

from .api_errors import (
    AlreadyMember,
    InvalidInvitation,
    InvitationEmailMismatch,
)
from .membership_changes import ensure_actor_grants
from .models import Invitation, Membership
from .organization_events import emit_member_added

TOKEN_BYTES = 32
INVITATION_EMAIL_TEMPLATE = "organizations/emails/invitation"


# The token is 32 random bytes: a fast hash is enough, as with API keys.
def hash_invitation_token(raw_token):
    return hashlib.sha256(raw_token.encode()).hexdigest()


def issue_invitation(organization, details, invited_by):
    email = get_user_model().objects.normalize_email(details["email"])
    raw_token = secrets.token_urlsafe(TOKEN_BYTES)
    with transaction.atomic():
        find_open_invitations(organization, email).update(revoked_at=timezone.now())
        invitation = Invitation.objects.create(
            organization=organization,
            email=email,
            role=details["role"],
            invited_by=invited_by,
            token_hash=hash_invitation_token(raw_token),
            expires_at=timezone.now()
            + timedelta(seconds=settings.TENANCY_INVITATION_TIMEOUT),
        )
    return invitation, raw_token


def invite_member_as(actor, details):
    ensure_actor_grants(actor, details["role"])
    if is_member(actor.organization, details["email"]):
        raise AlreadyMember
    invitation, raw_token = issue_invitation(actor.organization, details, actor.user)
    send_invitation_email(invitation, raw_token)
    return invitation


def send_invitation_email(invitation, raw_token):
    context = {
        "organization_name": invitation.organization.name,
        "inviter_email": getattr(invitation.invited_by, "email", ""),
        "role": invitation.get_role_display(),
        "invitation_url": settings.FRONTEND_INVITATION_URL.replace(
            "{token}", raw_token
        ),
        "timeout_hours": settings.TENANCY_INVITATION_TIMEOUT // 3600,
    }
    send_templated_email(INVITATION_EMAIL_TEMPLATE, invitation.email, context)


def find_open_invitations(organization, email):
    open_invitations = organization.invitations.filter(
        accepted_at__isnull=True, revoked_at__isnull=True
    )
    return open_invitations.filter(email__iexact=email)


def is_member(organization, email):
    return organization.memberships.filter(user__email__iexact=email).exists()


def find_pending_invitation(raw_token, lock=False):
    invitations = Invitation.objects.select_related("organization")
    if lock:
        invitations = invitations.select_for_update(of=("self",))
    invitation = invitations.filter(token_hash=hash_invitation_token(raw_token)).first()
    if invitation is None or invitation.status != Invitation.PENDING:
        raise InvalidInvitation
    return invitation


def describe_invitation(raw_token):
    invitation = find_pending_invitation(raw_token)
    account_exists = get_user_model().objects.is_email_taken(invitation.email)
    return {"invitation": invitation, "account_exists": account_exists}


def accept_invitation(user, raw_token):
    with transaction.atomic():
        invitation = find_pending_invitation(raw_token, lock=True)
        if invitation.email.lower() != user.email.lower():
            raise InvitationEmailMismatch
        return admit_member(invitation, user)


# Following the emailed link proves the address is real, so the account starts verified and
# is created even when the public registration is closed.
def register_from_invitation(raw_token, account):
    with transaction.atomic():
        invitation = find_pending_invitation(raw_token, lock=True)
        if get_user_model().objects.is_email_taken(invitation.email):
            raise AccountExists
        validate_password_for_new_user({**account, "email": invitation.email})
        user = get_user_model().objects.create_user(
            email=invitation.email, is_email_verified=True, **account
        )
        emit_account_event(USER_REGISTERED, user)
        return admit_member(invitation, user)


def admit_member(invitation, user):
    if Membership.objects.filter(
        organization=invitation.organization, user=user
    ).exists():
        raise AlreadyMember
    membership = Membership.objects.create(
        organization=invitation.organization, user=user, role=invitation.role
    )
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at", "updated_at"])
    emit_member_added(membership)
    return membership


def revoke_invitations(invitations):
    pending = invitations.filter(accepted_at__isnull=True, revoked_at__isnull=True)
    return pending.update(revoked_at=timezone.now())

from django.test import override_settings

from organizations.invitations import issue_invitation
from security.tests.test_throttling import override_rates

INVITATION_URL = "https://app.example.com/join?token={token}"

with_invitations = override_settings(
    TENANCY_ENABLED=True,
    FRONTEND_INVITATION_URL=INVITATION_URL,
    EMAIL_SEND_IN_BACKGROUND=False,
)
without_invitation_limit = override_rates(invitation=None)


def invite(organization, email, role="member"):
    return issue_invitation(
        organization, {"email": email, "role": role}, invited_by=None
    )


def token_from_email(message):
    return message.body.split("token=")[1].split()[0]

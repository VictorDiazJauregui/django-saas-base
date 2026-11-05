from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiResponse, extend_schema

from core.api_schema import RETRY_AFTER_HEADER, error_responses
from security.api_docs import EXAMPLE_PASSWORD, request_example

from .api_docs import MODULE_OFF, ORGANIZATION_ERRORS, ORGANIZATIONS_TAG
from .serializers import (
    InvitationLookupSerializer,
    InvitationRegisterSerializer,
    InvitationSerializer,
    InvitationTokenSerializer,
    MyOrganizationSerializer,
)

INVITATIONS_TAG = "invitations"
EXAMPLE_TOKEN = (
    "Zk3q8VxN2mBf0rT6yLw1Hc9Ju4Ad7Ps5Eg2Ki0Ox8Qn"  # noqa: S105 - shown in the docs only
)
TOKEN_EXAMPLE = request_example({"token": EXAMPLE_TOKEN})
PUBLIC_ERRORS = ("invalid", "invalid_invitation", "not_found", "throttled")

invitation_list_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("List the pending invitations"),
    description=_("Admins and owners only. ") + MODULE_OFF,
    responses={
        200: InvitationSerializer(many=True),
        **error_responses("permission_denied", *ORGANIZATION_ERRORS),
    },
)

invitation_create_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("Invite someone by email"),
    description=_(
        "Emails a link to FRONTEND_INVITATION_URL. A new invitation to the same email "
        "replaces the pending one. Only an owner invites owners. "
    )
    + MODULE_OFF,
    examples=[request_example({"email": "jane@example.com", "role": "member"})],
    responses={
        201: InvitationSerializer,
        **error_responses(
            "invalid", "permission_denied", "already_member", *ORGANIZATION_ERRORS
        ),
    },
)

invitation_revoke_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("Revoke a pending invitation"),
    description=_("Admins and owners only. ") + MODULE_OFF,
    responses={
        204: OpenApiResponse(description=_("Revoked.")),
        **error_responses("permission_denied", "not_found", *ORGANIZATION_ERRORS),
    },
)

invitation_lookup_schema = extend_schema(
    tags=[INVITATIONS_TAG],
    summary=_("Describe an invitation"),
    description=_(
        "Public. With account_exists the frontend shows a login or a sign-up form. "
    )
    + MODULE_OFF,
    request=InvitationTokenSerializer,
    examples=[TOKEN_EXAMPLE],
    parameters=[RETRY_AFTER_HEADER],
    responses={200: InvitationLookupSerializer, **error_responses(*PUBLIC_ERRORS)},
)

invitation_accept_schema = extend_schema(
    tags=[INVITATIONS_TAG],
    summary=_("Accept an invitation"),
    description=_("The logged-in user must have the invited email. ") + MODULE_OFF,
    request=InvitationTokenSerializer,
    examples=[TOKEN_EXAMPLE],
    parameters=[RETRY_AFTER_HEADER],
    responses={
        200: MyOrganizationSerializer,
        **error_responses(
            "not_authenticated",
            "token_not_valid",
            "invitation_email_mismatch",
            "already_member",
            *PUBLIC_ERRORS,
        ),
    },
)

invitation_register_schema = extend_schema(
    tags=[INVITATIONS_TAG],
    summary=_("Create the account from an invitation"),
    description=_(
        "Public, also with the public registration closed. The account starts verified; "
        "log in afterwards. "
    )
    + MODULE_OFF,
    request=InvitationRegisterSerializer,
    examples=[
        request_example(
            {
                "token": EXAMPLE_TOKEN,
                "password": EXAMPLE_PASSWORD,
                "password2": EXAMPLE_PASSWORD,
                "first_name": "Jane",
                "last_name": "Doe",
            }
        )
    ],
    parameters=[RETRY_AFTER_HEADER],
    responses={
        201: MyOrganizationSerializer,
        **error_responses("account_exists", *PUBLIC_ERRORS),
    },
)

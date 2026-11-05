from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiResponse, extend_schema

from core.api_schema import error_responses
from security.api_docs import request_example

from .serializers import (
    MemberSerializer,
    MyOrganizationSerializer,
    OrganizationSerializer,
)

ORGANIZATIONS_TAG = "organizations"
MODULE_OFF = _("Answers 404 unless TENANCY_ENABLED=True.")
ORGANIZATION_ERRORS = (
    "not_authenticated",
    "token_not_valid",
    "organization_not_found",
    "organization_api_key_not_allowed",
)

organization_list_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("List my organizations"),
    description=_(
        "The organizations the user belongs to, with the user's role in each. "
    )
    + MODULE_OFF,
    responses={
        200: MyOrganizationSerializer(many=True),
        **error_responses("not_authenticated", "token_not_valid", "not_found"),
    },
)

organization_create_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("Create an organization"),
    description=_(
        "The user who creates it becomes its owner. Without a slug, it comes from the name. "
    )
    + MODULE_OFF,
    request=OrganizationSerializer,
    examples=[request_example({"name": "Acme Corp"})],
    responses={
        201: OrganizationSerializer,
        **error_responses(
            "invalid", "not_authenticated", "token_not_valid", "not_found"
        ),
    },
)

organization_read_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("Get an organization"),
    description=MODULE_OFF,
    responses={200: OrganizationSerializer, **error_responses(*ORGANIZATION_ERRORS)},
)

organization_update_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("Rename an organization"),
    description=_("Admins and owners only. ") + MODULE_OFF,
    examples=[request_example({"name": "Acme Holdings", "slug": "acme-holdings"})],
    responses={
        200: OrganizationSerializer,
        **error_responses("invalid", "permission_denied", *ORGANIZATION_ERRORS),
    },
)

member_list_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("List the members of an organization"),
    description=MODULE_OFF,
    responses={
        200: MemberSerializer(many=True),
        **error_responses(*ORGANIZATION_ERRORS),
    },
)

member_update_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("Change the role of a member"),
    description=_(
        "Admins change members and admins; only an owner gives or takes the owner role. "
    )
    + MODULE_OFF,
    examples=[request_example({"role": "admin"})],
    responses={
        200: MemberSerializer,
        **error_responses(
            "invalid",
            "permission_denied",
            "not_found",
            "last_owner",
            *ORGANIZATION_ERRORS,
        ),
    },
)

member_remove_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("Remove a member, or leave the organization"),
    description=_(
        "Admins remove members and admins; only an owner removes an owner. Any member "
        "removes their own membership to leave. "
    )
    + MODULE_OFF,
    responses={
        204: OpenApiResponse(description=_("Removed.")),
        **error_responses(
            "permission_denied", "not_found", "last_owner", *ORGANIZATION_ERRORS
        ),
    },
)

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiResponse, extend_schema

from core.api_schema import error_responses
from security.api_docs import request_example

from .api_docs import ORGANIZATION_ERRORS, ORGANIZATIONS_TAG
from .serializers import (
    CreatedOrganizationApiKeySerializer,
    OrganizationApiKeySerializer,
)

API_KEYS_OFF = _("Answers 404 unless TENANCY_ENABLED=True and API_KEYS_ENABLED=True.")

organization_api_key_list_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("List the API keys of the organization"),
    description=_("Admins and owners only. Active and revoked keys, never the key. ")
    + API_KEYS_OFF,
    responses={
        200: OrganizationApiKeySerializer(many=True),
        **error_responses("permission_denied", *ORGANIZATION_ERRORS),
    },
)

organization_api_key_create_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("Create an API key of the organization"),
    description=_(
        "Admins and owners only. The answer is the only place the key shows up: it is "
        "not stored. The role is admin or member, never owner. "
    )
    + API_KEYS_OFF,
    examples=[request_example({"name": "ERP", "role": "member", "expires_at": None})],
    responses={
        201: CreatedOrganizationApiKeySerializer,
        **error_responses("invalid", "permission_denied", *ORGANIZATION_ERRORS),
    },
)

organization_api_key_revoke_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("Revoke an API key of the organization"),
    description=_(
        "Admins and owners only. The key stops working at once; the record stays. "
    )
    + API_KEYS_OFF,
    responses={
        204: OpenApiResponse(description=_("Revoked.")),
        **error_responses("permission_denied", "not_found", *ORGANIZATION_ERRORS),
    },
)

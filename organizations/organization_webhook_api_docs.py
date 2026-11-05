from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiResponse, extend_schema

from core.api_schema import error_responses
from security.api_docs import request_example

from .api_docs import ORGANIZATION_ERRORS, ORGANIZATIONS_TAG
from .organization_webhook_serializers import (
    CreatedOrganizationWebhookEndpointSerializer,
    OrganizationWebhookDeliverySerializer,
    OrganizationWebhookEndpointSerializer,
)

WEBHOOKS_OFF = _("Answers 404 unless TENANCY_ENABLED=True and WEBHOOKS_ENABLED=True.")
ADMINS_ONLY = _("Admins and owners only. ")
ENDPOINT_EXAMPLE = {
    "url": "https://erp.example.com/hooks",
    "events": ["organization.member_added", "organization.member_removed"],
    "description": "ERP",
}

webhook_list_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("List the webhook endpoints of the organization"),
    description=ADMINS_ONLY + _("Never the secret. ") + WEBHOOKS_OFF,
    responses={
        200: OrganizationWebhookEndpointSerializer(many=True),
        **error_responses("permission_denied", *ORGANIZATION_ERRORS),
    },
)

webhook_create_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("Create a webhook endpoint of the organization"),
    description=ADMINS_ONLY
    + _(
        "It receives only the events of this organization, from "
        "WEBHOOK_ORGANIZATION_EVENTS. The answer is the only place the secret shows up "
        "besides a rotation. "
    )
    + WEBHOOKS_OFF,
    request=OrganizationWebhookEndpointSerializer,
    examples=[request_example(ENDPOINT_EXAMPLE)],
    responses={
        201: CreatedOrganizationWebhookEndpointSerializer,
        **error_responses(
            "invalid",
            "permission_denied",
            "webhook_endpoint_limit_reached",
            *ORGANIZATION_ERRORS,
        ),
    },
)

webhook_read_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("Get a webhook endpoint of the organization"),
    description=ADMINS_ONLY + WEBHOOKS_OFF,
    responses={
        200: OrganizationWebhookEndpointSerializer,
        **error_responses("permission_denied", "not_found", *ORGANIZATION_ERRORS),
    },
)

webhook_update_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("Change a webhook endpoint of the organization"),
    description=ADMINS_ONLY + WEBHOOKS_OFF,
    examples=[request_example({"is_active": False})],
    responses={
        200: OrganizationWebhookEndpointSerializer,
        **error_responses(
            "invalid", "permission_denied", "not_found", *ORGANIZATION_ERRORS
        ),
    },
)

webhook_delete_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("Delete a webhook endpoint of the organization"),
    description=ADMINS_ONLY + _("Its deliveries are deleted with it. ") + WEBHOOKS_OFF,
    responses={
        204: OpenApiResponse(description=_("Deleted.")),
        **error_responses("permission_denied", "not_found", *ORGANIZATION_ERRORS),
    },
)

webhook_rotate_secret_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("Rotate the secret of a webhook endpoint"),
    description=ADMINS_ONLY
    + _(
        "The old secret stops signing at once, pending retries included. The answer is "
        "the only place the new one shows up. "
    )
    + WEBHOOKS_OFF,
    request=None,
    responses={
        200: CreatedOrganizationWebhookEndpointSerializer,
        **error_responses("permission_denied", "not_found", *ORGANIZATION_ERRORS),
    },
)

webhook_delivery_list_schema = extend_schema(
    tags=[ORGANIZATIONS_TAG],
    summary=_("List the deliveries of a webhook endpoint"),
    description=ADMINS_ONLY + _("Newest first, read only. ") + WEBHOOKS_OFF,
    responses={
        200: OrganizationWebhookDeliverySerializer(many=True),
        **error_responses("permission_denied", "not_found", *ORGANIZATION_ERRORS),
    },
)

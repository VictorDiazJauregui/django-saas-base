from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException, PermissionDenied

from .membership_changes import LastOwnerError
from .organization_webhooks import WebhookEndpointLimitReached


class LastOwnerConflict(APIException):
    status_code = 409
    default_detail = LastOwnerError.message
    default_code = "last_owner"


# One answer for a token that never existed, expired, was revoked or was used: the caller
# learns nothing about invitations it doesn't hold.
class InvalidInvitation(APIException):
    status_code = 400
    default_detail = _("This invitation is not valid or has expired.")
    default_code = "invalid_invitation"


class InvitationEmailMismatch(APIException):
    status_code = 403
    default_detail = _("This invitation is for another email address.")
    default_code = "invitation_email_mismatch"


class AlreadyMember(APIException):
    status_code = 409
    default_detail = _("This person is already a member of the organization.")
    default_code = "already_member"


# Keys reach the data of their organization; the module itself is managed by people only.
class OrganizationApiKeyNotAllowed(PermissionDenied):
    default_detail = _("Organization API keys can't use this route.")
    default_code = "organization_api_key_not_allowed"


class WebhookEndpointLimitConflict(APIException):
    status_code = 409
    default_detail = WebhookEndpointLimitReached.message
    default_code = "webhook_endpoint_limit_reached"

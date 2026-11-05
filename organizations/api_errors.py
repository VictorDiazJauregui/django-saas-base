from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException

from .membership_changes import LastOwnerError


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

from axes.helpers import get_cool_off
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import Throttled

LOCKOUT_TEMPLATE = "security/lockout.html"
SUBMITTED_EMAIL_FIELDS = ("email", "username")


class AccountLockedOut(Throttled):
    default_detail = _("Too many failed login attempts.")
    default_code = "account_locked_out"


def read_submitted_email(request, credentials):
    submitted = credentials or getattr(request, "data", request.POST)
    return next(
        (
            submitted.get(field)
            for field in SUBMITTED_EMAIL_FIELDS
            if submitted.get(field)
        ),
        "",
    )


# The admin sends the email as "username" and the API as "email". Both are lowercased like
# the stored emails, so changing the case does not start a fresh count.
def get_lockout_username(request, credentials=None):
    submitted_email = read_submitted_email(request, credentials)
    return get_user_model().objects.normalize_email(submitted_email) or None


def cool_off_seconds(request):
    return int(get_cool_off(request).total_seconds())


# axes flags the request it authenticates, and in the API that is DRF's request, which
# AxesMiddleware never sees: the API has to turn the flag into the response itself.
def raise_if_locked_out(request):
    if getattr(request, "axes_locked_out", False):
        raise AccountLockedOut(wait=cool_off_seconds(request))


def render_admin_lockout(request, original_response=None, credentials=None):
    context = {"cool_off_minutes": cool_off_seconds(request) // 60}
    return render(
        request, LOCKOUT_TEMPLATE, context, status=AccountLockedOut.status_code
    )

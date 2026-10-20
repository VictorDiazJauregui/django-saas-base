from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from core.api_schema import RETRY_AFTER_HEADER, error_responses

from .api_docs import AUTH_TAG, LOGIN_ANSWER_RESPONSE, request_example
from .google_login import log_in_with_google
from .two_factor import build_login_answer
from .views import PublicAccountView


class GoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField(write_only=True)


google_login_schema = extend_schema(
    tags=[AUTH_TAG],
    summary=_("Log in with Google"),
    description=_(
        "Takes the id_token Google Identity Services gives the frontend and answers like "
        "the email login: the tokens, or the second-factor challenge. A new email creates "
        "an account only while public registration is open. Answers 404 unless "
        "GOOGLE_CLIENT_IDS is set."
    ),
    parameters=[RETRY_AFTER_HEADER],
    examples=[request_example({"id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6Ii4uLiJ9..."})],
    responses={
        200: LOGIN_ANSWER_RESPONSE,
        **error_responses(
            "invalid",
            "invalid_google_token",
            "no_active_account",
            "permission_denied",
            "account_exists",
            "not_found",
            "throttled",
            "google_unavailable",
        ),
    },
)


@google_login_schema
class GoogleLoginView(PublicAccountView):
    serializer_class = GoogleLoginSerializer
    throttle_scope = "login"

    def initial(self, request, *args, **kwargs):
        if not settings.GOOGLE_CLIENT_IDS:
            raise NotFound
        super().initial(request, *args, **kwargs)

    def post(self, request):
        user = log_in_with_google(self.validated_data(request)["id_token"])
        request._request.user_for_audit = user
        answer = build_login_answer(user)
        if "access" in answer:
            user_logged_in.send(sender=user.__class__, request=request, user=user)
        return Response(answer)

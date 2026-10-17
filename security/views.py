from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_view
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from .api_docs import (
    document_password_reset,
    document_resend_verification,
    login_schema,
    logout_schema,
    password_change_schema,
    password_reset_confirm_schema,
    profile_read_schema,
    profile_update_schema,
    refresh_schema,
    register_schema,
    verify_email_schema,
)
from .email_verification import mark_email_verified, resend_verification
from .password_change import set_new_password
from .password_reset import complete_password_reset, request_password_reset
from .permissions import PublicRegistrationEnabled
from .security_events import log_token_revoked
from .serializers import (
    EmailVerificationSerializer,
    LockoutAwareTokenObtainPairSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    ResendVerificationSerializer,
    UserRegisterSerializer,
)
from .token_owner import find_token_owner

User = get_user_model()


@register_schema
class UserRegisterView(generics.CreateAPIView):
    """
    API view for user registration.
    """

    queryset = User.objects.all()
    permission_classes = (PublicRegistrationEnabled,)
    serializer_class = UserRegisterSerializer
    throttle_scope = "register"

    # DRF answers an anonymous request that lacks permission with 401, asking for credentials.
    # No token opens a closed registration, so the answer is 403.
    def permission_denied(self, request, message=None, code=None):
        raise PermissionDenied(detail=message, code=code)


@login_schema
class CustomLoginView(TokenObtainPairView):
    """
    Custom login view.
    After a successful login, it attaches the authenticated user to the request
    so the AuditMiddleware can log which user performed the login action.
    """

    throttle_scope = "login"
    serializer_class = LockoutAwareTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK:
            return response
        user = find_token_owner(AccessToken, response.data.get("access"))
        request._request.user_for_audit = user
        if user is not None:
            # SimpleJWT does not send it: Django updates last_login and axes resets the
            # failure count of the account, as after an admin login.
            user_logged_in.send(sender=user.__class__, request=request, user=user)
        return response


# Public like SimpleJWT's view: holding the refresh token is enough to use it, so it is
# enough to revoke it, and logging out keeps working after the access token expired.
@logout_schema
class LogoutView(TokenBlacklistView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        refresh_token = request.data.get("refresh")
        owner = find_token_owner(RefreshToken, refresh_token)
        request._request.user_for_audit = owner
        if response.status_code == status.HTTP_200_OK:
            log_token_revoked(owner, "logout")
        return response


# Email changes are left out: they need the new address verified first.
@extend_schema_view(get=profile_read_schema, patch=profile_update_schema)
class ProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = ProfileSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


@password_change_schema
class PasswordChangeView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = PasswordChangeSerializer
    throttle_scope = "password"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        set_new_password(request.user, serializer.validated_data["new_password"])
        return Response(status=status.HTTP_204_NO_CONTENT)


# Public routes that don't need to know who calls: a stale Authorization header sent by a
# frontend must not turn a password reset into a 401.
class PublicAccountView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def validated_data(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


@document_password_reset
class PasswordResetRequestView(PublicAccountView):
    serializer_class = PasswordResetRequestSerializer
    throttle_scope = "password"
    answer = _("If the email belongs to an account, a reset link is on its way.")

    def post(self, request):
        request_password_reset(self.validated_data(request)["email"])
        return Response({"detail": self.answer})


@password_reset_confirm_schema
class PasswordResetConfirmView(PublicAccountView):
    serializer_class = PasswordResetConfirmSerializer
    throttle_scope = "password"

    def post(self, request):
        validated = self.validated_data(request)
        complete_password_reset(validated["user"], validated["new_password"])
        request._request.user_for_audit = validated["user"]
        return Response(status=status.HTTP_204_NO_CONTENT)


@verify_email_schema
class EmailVerificationView(PublicAccountView):
    serializer_class = EmailVerificationSerializer
    throttle_scope = "verify_email"

    def post(self, request):
        mark_email_verified(self.validated_data(request)["user"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@document_resend_verification
class ResendVerificationView(PublicAccountView):
    serializer_class = ResendVerificationSerializer
    throttle_scope = "verify_email"
    answer = _(
        "If the email belongs to an account pending verification, a new link is on its way."
    )

    def post(self, request):
        resend_verification(self.validated_data(request)["email"])
        return Response({"detail": self.answer})


# SimpleJWT's view, documented here instead of decorating the library's class.
@refresh_schema
class TokenPairRefreshView(TokenRefreshView):
    pass

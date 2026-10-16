from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView

from .permissions import PublicRegistrationEnabled
from .serializers import (
    LockoutAwareTokenObtainPairSerializer,
    ProfileSerializer,
    UserRegisterSerializer,
)
from .token_owner import find_token_owner

User = get_user_model()


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
class LogoutView(TokenBlacklistView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        refresh_token = request.data.get("refresh")
        request._request.user_for_audit = find_token_owner(RefreshToken, refresh_token)
        return response


# Email changes are left out: they need the new address verified first.
class ProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = ProfileSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user

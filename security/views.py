from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import LockoutAwareTokenObtainPairSerializer, UserRegisterSerializer

User = get_user_model()


class UserRegisterView(generics.CreateAPIView):
    """
    API view for user registration.
    """

    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = UserRegisterSerializer
    throttle_scope = "register"


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
        user = self.find_token_owner(response)
        request._request.user_for_audit = user
        if user is not None:
            # SimpleJWT does not send it: Django updates last_login and axes resets the
            # failure count of the account, as after an admin login.
            user_logged_in.send(sender=user.__class__, request=request, user=user)
        return response

    def find_token_owner(self, response):
        try:
            token = AccessToken(response.data.get("access"))
            return User.objects.get(id=token.payload.get("user_id"))
        except (TokenError, User.DoesNotExist):
            return None

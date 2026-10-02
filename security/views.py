from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import UserRegisterSerializer

User = get_user_model()


class UserRegisterView(generics.CreateAPIView):
    """
    API view for user registration.
    """

    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = UserRegisterSerializer


class CustomLoginView(TokenObtainPairView):
    """
    Custom login view.
    After a successful login, it attaches the authenticated user to the request
    so the AuditMiddleware can log which user performed the login action.
    """

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            request._request.user_for_audit = self.find_token_owner(response)
        return response

    def find_token_owner(self, response):
        try:
            token = AccessToken(response.data.get("access"))
            return User.objects.get(id=token.payload.get("user_id"))
        except (TokenError, User.DoesNotExist):
            return None

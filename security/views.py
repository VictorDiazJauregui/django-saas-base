from django.contrib.auth import get_user_model
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import AccessToken

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

        if response.status_code == 200:
            try:
                access_token = response.data.get('access')
                token = AccessToken(access_token)
                user_id = token.payload.get('user_id')
                user = User.objects.get(id=user_id)
                # Attach user to the original Django request for the audit middleware
                request._request.user_for_audit = user
            except Exception:
                # If anything goes wrong, we just don't attach the user.
                # The audit log will record the user as anonymous, but it won't crash.
                request._request.user_for_audit = None

        return response


# Note: Password recovery views are not implemented here but can be added.
# Django's built-in 'django.contrib.auth.views' can be used for this,
# or you can use a library like 'django-rest-passwordreset'.
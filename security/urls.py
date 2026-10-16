from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import CustomLoginView, LogoutView, ProfileView, UserRegisterView

app_name = "security"

urlpatterns = [
    path("register/", UserRegisterView.as_view(), name="register"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("login/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", ProfileView.as_view(), name="me"),
]

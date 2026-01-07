from django.urls import path
from .views import UserRegisterView, CustomLoginView
from rest_framework_simplejwt.views import TokenRefreshView

app_name = "security"

urlpatterns = [
    path("register/", UserRegisterView.as_view(), name="register"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("login/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]

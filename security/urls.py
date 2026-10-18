from django.urls import path

from .views import (
    CustomLoginView,
    EmailVerificationView,
    LogoutView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ProfileView,
    ResendVerificationView,
    TokenPairRefreshView,
    UserRegisterView,
)

app_name = "security"

urlpatterns = [
    path("register/", UserRegisterView.as_view(), name="register"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("login/refresh/", TokenPairRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", ProfileView.as_view(), name="me"),
    path("password/change/", PasswordChangeView.as_view(), name="password_change"),
    path("password/reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path(
        "password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("verify-email/", EmailVerificationView.as_view(), name="verify_email"),
    path(
        "verify-email/resend/",
        ResendVerificationView.as_view(),
        name="resend_verification",
    ),
]

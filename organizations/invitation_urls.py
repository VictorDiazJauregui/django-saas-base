from django.urls import path

from .invitation_views import (
    InvitationAcceptView,
    InvitationLookupView,
    InvitationRegisterView,
)

app_name = "invitations"

urlpatterns = [
    path("lookup/", InvitationLookupView.as_view(), name="lookup"),
    path("accept/", InvitationAcceptView.as_view(), name="accept"),
    path("register/", InvitationRegisterView.as_view(), name="register"),
]

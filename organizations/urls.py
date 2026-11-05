from django.urls import path

from .invitation_views import InvitationListCreateView, InvitationRevokeView
from .organization_views import (
    MemberDetailView,
    MemberListView,
    OrganizationDetailView,
    OrganizationListCreateView,
)

app_name = "organizations"

urlpatterns = [
    path("", OrganizationListCreateView.as_view(), name="list"),
    path("<uuid:organization_id>/", OrganizationDetailView.as_view(), name="detail"),
    path("<uuid:organization_id>/members/", MemberListView.as_view(), name="members"),
    path(
        "<uuid:organization_id>/members/<uuid:membership_id>/",
        MemberDetailView.as_view(),
        name="member",
    ),
    path(
        "<uuid:organization_id>/invitations/",
        InvitationListCreateView.as_view(),
        name="invitations",
    ),
    path(
        "<uuid:organization_id>/invitations/<uuid:invitation_id>/",
        InvitationRevokeView.as_view(),
        name="invitation",
    ),
]

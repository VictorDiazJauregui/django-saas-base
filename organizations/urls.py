from django.urls import path

from .invitation_views import InvitationListCreateView, InvitationRevokeView
from .organization_api_key_views import (
    OrganizationApiKeyListCreateView,
    OrganizationApiKeyRevokeView,
)
from .organization_views import (
    MemberDetailView,
    MemberListView,
    OrganizationDetailView,
    OrganizationListCreateView,
)
from .organization_webhook_views import (
    OrganizationWebhookDeliveryListView,
    OrganizationWebhookDetailView,
    OrganizationWebhookListCreateView,
    OrganizationWebhookRotateSecretView,
)

app_name = "organizations"

urlpatterns = [
    path("", OrganizationListCreateView.as_view(), name="list"),
    path(
        "<organization:organization_id>/",
        OrganizationDetailView.as_view(),
        name="detail",
    ),
    path(
        "<organization:organization_id>/members/",
        MemberListView.as_view(),
        name="members",
    ),
    path(
        "<organization:organization_id>/members/<uuid:membership_id>/",
        MemberDetailView.as_view(),
        name="member",
    ),
    path(
        "<organization:organization_id>/invitations/",
        InvitationListCreateView.as_view(),
        name="invitations",
    ),
    path(
        "<organization:organization_id>/invitations/<uuid:invitation_id>/",
        InvitationRevokeView.as_view(),
        name="invitation",
    ),
    path(
        "<organization:organization_id>/api-keys/",
        OrganizationApiKeyListCreateView.as_view(),
        name="api_keys",
    ),
    path(
        "<organization:organization_id>/api-keys/<uuid:key_id>/",
        OrganizationApiKeyRevokeView.as_view(),
        name="api_key",
    ),
    path(
        "<organization:organization_id>/webhooks/",
        OrganizationWebhookListCreateView.as_view(),
        name="webhooks",
    ),
    path(
        "<organization:organization_id>/webhooks/<uuid:endpoint_id>/",
        OrganizationWebhookDetailView.as_view(),
        name="webhook",
    ),
    path(
        "<organization:organization_id>/webhooks/<uuid:endpoint_id>/rotate-secret/",
        OrganizationWebhookRotateSecretView.as_view(),
        name="webhook_rotate_secret",
    ),
    path(
        "<organization:organization_id>/webhooks/<uuid:endpoint_id>/deliveries/",
        OrganizationWebhookDeliveryListView.as_view(),
        name="webhook_deliveries",
    ),
]

from django.utils import timezone
from drf_spectacular.utils import extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from security.views import PublicAccountView

from .invitation_api_docs import (
    invitation_accept_schema,
    invitation_create_schema,
    invitation_list_schema,
    invitation_lookup_schema,
    invitation_register_schema,
    invitation_revoke_schema,
)
from .invitations import (
    accept_invitation,
    describe_invitation,
    invite_member_as,
    register_from_invitation,
    revoke_invitations,
)
from .models import Invitation
from .organization_views import TenancyModuleMixin, membership_change_errors
from .permissions import HasOrganizationRole
from .roles import OrganizationRole
from .serializers import (
    InvitationLookupSerializer,
    InvitationRegisterSerializer,
    InvitationSerializer,
    InvitationTokenSerializer,
    MyOrganizationSerializer,
)


class PendingInvitationsMixin(TenancyModuleMixin):
    permission_classes = (HasOrganizationRole(OrganizationRole.ADMIN),)
    serializer_class = InvitationSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Invitation.objects.none()
        pending = self.request.organization.invitations.filter(
            accepted_at__isnull=True,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        return pending.select_related("invited_by")


@extend_schema_view(get=invitation_list_schema, post=invitation_create_schema)
class InvitationListCreateView(PendingInvitationsMixin, generics.ListAPIView):
    def post(self, request, organization_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with membership_change_errors():
            invitation = invite_member_as(request.membership, serializer.validated_data)
        return Response(
            self.get_serializer(invitation).data, status=status.HTTP_201_CREATED
        )


@extend_schema_view(delete=invitation_revoke_schema)
class InvitationRevokeView(PendingInvitationsMixin, generics.GenericAPIView):
    lookup_url_kwarg = "invitation_id"

    def delete(self, request, organization_id, invitation_id):
        invitation = self.get_object()
        revoke_invitations(Invitation.objects.filter(pk=invitation.pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicInvitationView(TenancyModuleMixin, PublicAccountView):
    throttle_scope = "invitation"


@extend_schema_view(post=invitation_lookup_schema)
class InvitationLookupView(PublicInvitationView):
    serializer_class = InvitationTokenSerializer

    def post(self, request):
        description = describe_invitation(self.validated_data(request)["token"])
        return Response(InvitationLookupSerializer(description).data)


@extend_schema_view(post=invitation_accept_schema)
class InvitationAcceptView(TenancyModuleMixin, generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = InvitationTokenSerializer
    throttle_scope = "invitation"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = accept_invitation(request.user, serializer.validated_data["token"])
        return Response(MyOrganizationSerializer(membership).data)


@extend_schema_view(post=invitation_register_schema)
class InvitationRegisterView(PublicInvitationView):
    serializer_class = InvitationRegisterSerializer

    def post(self, request):
        account = self.validated_data(request)
        token = account.pop("token")
        account.pop("password2")
        membership = register_from_invitation(token, account)
        request._request.user_for_audit = membership.user
        answer = MyOrganizationSerializer(membership).data
        return Response(answer, status=status.HTTP_201_CREATED)

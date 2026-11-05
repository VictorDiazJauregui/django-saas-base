from contextlib import contextmanager

from django.conf import settings
from drf_spectacular.utils import extend_schema_view
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .api_docs import (
    member_list_schema,
    member_remove_schema,
    member_update_schema,
    organization_create_schema,
    organization_list_schema,
    organization_read_schema,
    organization_update_schema,
)
from .api_errors import LastOwnerConflict
from .membership_changes import (
    LastOwnerError,
    MembershipChangeDenied,
    change_member_role_as,
    remove_member_as,
)
from .models import Membership
from .organization_creation import create_organization_for
from .permissions import HasOrganizationRole, IsOrganizationMember
from .roles import OrganizationRole
from .serializers import (
    MemberSerializer,
    MyOrganizationSerializer,
    OrganizationSerializer,
)


# With the module off the routes don't exist, as before it was added.
class TenancyModuleMixin:
    def initial(self, request, *args, **kwargs):
        if not settings.TENANCY_ENABLED:
            raise NotFound
        super().initial(request, *args, **kwargs)


@contextmanager
def membership_change_errors():
    try:
        yield
    except MembershipChangeDenied as denied:
        raise PermissionDenied from denied
    except LastOwnerError as last_owner:
        raise LastOwnerConflict from last_owner


@extend_schema_view(get=organization_list_schema, post=organization_create_schema)
class OrganizationListCreateView(TenancyModuleMixin, generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = MyOrganizationSerializer

    def get_queryset(self):
        memberships = Membership.objects.select_related("organization")
        return memberships.filter(user=self.request.user).order_by("organization__name")

    def post(self, request):
        context = {"role": OrganizationRole.OWNER}
        serializer = OrganizationSerializer(data=request.data, context=context)
        serializer.is_valid(raise_exception=True)
        organization = create_organization_for(request.user, serializer.validated_data)
        answer = OrganizationSerializer(organization, context=context).data
        return Response(answer, status=status.HTTP_201_CREATED)


@extend_schema_view(get=organization_read_schema, patch=organization_update_schema)
class OrganizationDetailView(TenancyModuleMixin, generics.RetrieveUpdateAPIView):
    serializer_class = OrganizationSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [HasOrganizationRole(OrganizationRole.ADMIN)]
        return [IsOrganizationMember()]

    def get_object(self):
        return self.request.organization

    def get_serializer_context(self):
        membership = getattr(self.request, "membership", None)
        return {
            **super().get_serializer_context(),
            "role": getattr(membership, "role", ""),
        }


class OrganizationMembersMixin(TenancyModuleMixin):
    permission_classes = (IsOrganizationMember,)
    serializer_class = MemberSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Membership.objects.none()
        memberships = self.request.organization.memberships.select_related("user")
        return memberships.order_by("created_at")


@extend_schema_view(get=member_list_schema)
class MemberListView(OrganizationMembersMixin, generics.ListAPIView):
    pass


@extend_schema_view(patch=member_update_schema, delete=member_remove_schema)
class MemberDetailView(OrganizationMembersMixin, generics.GenericAPIView):
    lookup_url_kwarg = "membership_id"

    def patch(self, request, organization_id, membership_id):
        membership = self.get_object()
        serializer = self.get_serializer(membership, data=request.data)
        serializer.is_valid(raise_exception=True)
        with membership_change_errors():
            role = serializer.validated_data["role"]
            change_member_role_as(request.membership, membership, role)
        return Response(self.get_serializer(membership).data)

    def delete(self, request, organization_id, membership_id):
        membership = self.get_object()
        with membership_change_errors():
            remove_member_as(request.membership, membership)
        return Response(status=status.HTTP_204_NO_CONTENT)

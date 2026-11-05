from django.db import connection, models
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import Organization, OrganizationScopedModel
from organizations.permissions import HasOrganizationRole, IsOrganizationMember
from organizations.views import OrganizationScopedViewSet


class Project(OrganizationScopedModel):
    # DO_NOTHING keeps this test-only table out of the cascade of every other test, where the
    # table doesn't exist. The CASCADE of the real field has its own test.
    organization = models.ForeignKey(Organization, on_delete=models.DO_NOTHING)
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "organizations"


def create_project_table():
    with connection.schema_editor() as editor:
        editor.create_model(Project)


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "organization"]
        read_only_fields = ["organization"]


class ProjectViewSet(OrganizationScopedViewSet):
    queryset = Project.objects.order_by("name")
    serializer_class = ProjectSerializer


class MembershipEchoView(APIView):
    permission_classes = (IsOrganizationMember,)

    def get(self, request, organization_id):
        return Response(
            {"slug": request.organization.slug, "role": request.membership.role}
        )


class AdminOnlyView(MembershipEchoView):
    permission_classes = (HasOrganizationRole("admin"),)


class NonAdminView(MembershipEchoView):
    permission_classes = (IsAuthenticated & ~HasOrganizationRole("admin"),)

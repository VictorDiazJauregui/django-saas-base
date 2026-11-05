from rest_framework.viewsets import ModelViewSet

from .permissions import IsOrganizationMember


# The organization always comes from the URL, never from the body: a client can't read, write
# or move rows of an organization it doesn't belong to.
class OrganizationScopedMixin:
    permission_classes = (IsOrganizationMember,)

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        return queryset.filter(organization=self.request.organization)

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)

    def perform_update(self, serializer):
        serializer.save(organization=self.request.organization)


class OrganizationScopedViewSet(OrganizationScopedMixin, ModelViewSet):
    pass

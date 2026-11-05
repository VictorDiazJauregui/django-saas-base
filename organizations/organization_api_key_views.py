from django.conf import settings
from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema_view
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response

from .models import OrganizationApiKey
from .organization_api_key_api_docs import (
    organization_api_key_create_schema,
    organization_api_key_list_schema,
    organization_api_key_revoke_schema,
)
from .organization_api_keys import (
    issue_organization_api_key,
    revoke_organization_api_keys,
)
from .organization_views import TenancyModuleMixin
from .permissions import HasOrganizationRole
from .roles import OrganizationRole
from .serializers import (
    CreatedOrganizationApiKeySerializer,
    OrganizationApiKeySerializer,
)


class OrganizationApiKeysMixin(TenancyModuleMixin):
    permission_classes = (HasOrganizationRole(OrganizationRole.ADMIN),)
    serializer_class = OrganizationApiKeySerializer

    def initial(self, request: Request, *args, **kwargs) -> None:
        if not settings.API_KEYS_ENABLED:
            raise NotFound
        super().initial(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[OrganizationApiKey]:
        if getattr(self, "swagger_fake_view", False):
            return OrganizationApiKey.objects.none()
        api_keys = OrganizationApiKey.objects.select_related("created_by")
        return api_keys.filter(organization=self.request.organization)


@extend_schema_view(
    get=organization_api_key_list_schema, post=organization_api_key_create_schema
)
class OrganizationApiKeyListCreateView(OrganizationApiKeysMixin, generics.ListAPIView):
    def post(self, request: Request, organization_id: str) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        details = {**serializer.validated_data, "created_by": request.user}
        api_key, raw_key = issue_organization_api_key(request.organization, details)
        context = {**self.get_serializer_context(), "raw_key": raw_key}
        answer = CreatedOrganizationApiKeySerializer(api_key, context=context).data
        return Response(answer, status=status.HTTP_201_CREATED)


@extend_schema_view(delete=organization_api_key_revoke_schema)
class OrganizationApiKeyRevokeView(OrganizationApiKeysMixin, generics.GenericAPIView):
    lookup_url_kwarg = "key_id"

    def delete(self, request: Request, organization_id: str, key_id: str) -> Response:
        api_key = self.get_object()
        revoke_organization_api_keys(OrganizationApiKey.objects.filter(pk=api_key.pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

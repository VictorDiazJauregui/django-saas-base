from django.conf import settings
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema_view
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response

from webhooks.models import WebhookDelivery, WebhookEndpoint

from .api_errors import WebhookEndpointLimitConflict
from .organization_views import TenancyModuleMixin
from .organization_webhook_api_docs import (
    webhook_create_schema,
    webhook_delete_schema,
    webhook_delivery_list_schema,
    webhook_list_schema,
    webhook_read_schema,
    webhook_rotate_secret_schema,
    webhook_update_schema,
)
from .organization_webhook_serializers import (
    CreatedOrganizationWebhookEndpointSerializer,
    OrganizationWebhookDeliverySerializer,
    OrganizationWebhookEndpointSerializer,
)
from .organization_webhooks import (
    WebhookEndpointLimitReached,
    create_organization_webhook_endpoint,
    rotate_webhook_endpoint_secret,
)
from .permissions import HasOrganizationRole
from .roles import OrganizationRole


class OrganizationWebhooksMixin(TenancyModuleMixin):
    permission_classes = (HasOrganizationRole(OrganizationRole.ADMIN),)
    serializer_class = OrganizationWebhookEndpointSerializer
    lookup_url_kwarg = "endpoint_id"

    def initial(self, request: Request, *args, **kwargs) -> None:
        if not settings.WEBHOOKS_ENABLED:
            raise NotFound
        super().initial(request, *args, **kwargs)

    def find_organization_endpoints(self) -> QuerySet[WebhookEndpoint]:
        if getattr(self, "swagger_fake_view", False):
            return WebhookEndpoint.objects.none()
        return WebhookEndpoint.objects.filter(organization=self.request.organization)

    def get_queryset(self) -> QuerySet:
        return self.find_organization_endpoints()


@extend_schema_view(get=webhook_list_schema, post=webhook_create_schema)
class OrganizationWebhookListCreateView(
    OrganizationWebhooksMixin, generics.ListAPIView
):
    def post(self, request: Request, organization_id: str) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            endpoint = create_organization_webhook_endpoint(
                request.organization, serializer.validated_data
            )
        except WebhookEndpointLimitReached as limit_reached:
            raise WebhookEndpointLimitConflict from limit_reached
        answer = CreatedOrganizationWebhookEndpointSerializer(endpoint).data
        return Response(answer, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=webhook_read_schema, patch=webhook_update_schema, delete=webhook_delete_schema
)
class OrganizationWebhookDetailView(
    OrganizationWebhooksMixin, generics.RetrieveUpdateDestroyAPIView
):
    http_method_names = ["get", "patch", "delete", "head", "options"]


@extend_schema_view(post=webhook_rotate_secret_schema)
class OrganizationWebhookRotateSecretView(
    OrganizationWebhooksMixin, generics.GenericAPIView
):
    def post(
        self, request: Request, organization_id: str, endpoint_id: str
    ) -> Response:
        endpoint = rotate_webhook_endpoint_secret(self.get_object())
        return Response(CreatedOrganizationWebhookEndpointSerializer(endpoint).data)


@extend_schema_view(get=webhook_delivery_list_schema)
class OrganizationWebhookDeliveryListView(
    OrganizationWebhooksMixin, generics.ListAPIView
):
    serializer_class = OrganizationWebhookDeliverySerializer

    def get_queryset(self) -> QuerySet[WebhookDelivery]:
        if getattr(self, "swagger_fake_view", False):
            return WebhookDelivery.objects.none()
        endpoint_id = self.kwargs[self.lookup_url_kwarg]
        endpoint = get_object_or_404(self.find_organization_endpoints(), pk=endpoint_id)
        return endpoint.deliveries.all()

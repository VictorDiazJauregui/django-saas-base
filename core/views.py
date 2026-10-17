from django.utils.cache import add_never_cache_headers
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .health import HEALTHY, describe_health
from .health_schema import health_schema


class HealthView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = ()

    @health_schema
    def get(self, request):
        health = describe_health()
        healthy = health["status"] == HEALTHY
        answer_status = (
            status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        response = Response(health, status=answer_status)
        add_never_cache_headers(response)
        return response

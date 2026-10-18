from django.conf import settings
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission
from rest_framework.renderers import JSONRenderer
from rest_framework_simplejwt.authentication import JWTAuthentication


# Hidden docs answer the same 404 as a route that doesn't exist, so nobody learns they're there.
class ApiDocsAccess(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if settings.API_DOCS_ENABLED or (user.is_active and user.is_staff):
            return True
        raise NotFound


class ApiDocsViewMixin:
    permission_classes = (ApiDocsAccess,)
    # The session lets a staff user open the docs in the browser after logging in to the admin.
    authentication_classes = (SessionAuthentication, JWTAuthentication)

    # These views render YAML or an HTML page; their errors still have to be the JSON of the
    # rest of /api/, or a hidden route would answer a different 404 than a missing one.
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if response.exception:
            response.accepted_renderer = JSONRenderer()
            response.accepted_media_type = JSONRenderer.media_type
        return response


class ApiSchemaView(ApiDocsViewMixin, SpectacularAPIView):
    pass


class ApiDocsView(ApiDocsViewMixin, SpectacularSwaggerView):
    pass

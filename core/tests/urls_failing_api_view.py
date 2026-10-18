from django.urls import include, path

from core import urls as project_urls


class FailingApiViewError(Exception):
    pass


def failing_api_view(request):
    raise FailingApiViewError("Raised on purpose to check the 500 response of the API.")


handler404 = project_urls.handler404
handler500 = project_urls.handler500

urlpatterns = [
    path("api/v1/failing/", failing_api_view),
    path("failing/", failing_api_view),
    path("", include("core.urls")),
]

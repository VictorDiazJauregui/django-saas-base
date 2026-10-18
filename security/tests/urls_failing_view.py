from django.urls import include, path


class FailingViewError(Exception):
    pass


def failing_view(request):
    raise FailingViewError("Raised on purpose to check what the audit log stores.")


urlpatterns = [
    path("failing/", failing_view),
    path("", include("core.urls")),
]

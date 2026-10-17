from django.contrib import admin
from django.urls import include, path

from core.api_docs import ApiDocsView, ApiSchemaView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("security.urls", namespace="security")),
    path("api/schema/", ApiSchemaView.as_view(), name="schema"),
    path("api/docs/", ApiDocsView.as_view(url_name="schema"), name="docs"),
]

handler404 = "core.exceptions.api_not_found"
handler500 = "core.exceptions.api_server_error"

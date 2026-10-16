from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("security.urls", namespace="security")),
]

handler404 = "core.exceptions.api_not_found"
handler500 = "core.exceptions.api_server_error"

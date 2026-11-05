from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .scoped_project import (
    AdminOnlyView,
    MembershipEchoView,
    NonAdminView,
    ProjectViewSet,
)

router = SimpleRouter()
router.register("projects", ProjectViewSet, basename="project")

ORGANIZATION_PREFIX = "api/v1/organizations/<organization:organization_id>/"

urlpatterns = [
    path(ORGANIZATION_PREFIX, include(router.urls)),
    path(f"{ORGANIZATION_PREFIX}echo/", MembershipEchoView.as_view(), name="echo"),
    path(
        f"{ORGANIZATION_PREFIX}admin-only/", AdminOnlyView.as_view(), name="admin_only"
    ),
    path(f"{ORGANIZATION_PREFIX}non-admin/", NonAdminView.as_view(), name="non_admin"),
    path(
        "api/v1/raw/<str:organization_id>/echo/",
        MembershipEchoView.as_view(),
        name="raw_echo",
    ),
]

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from security.permissions import HasPermission, HasRole

from .user_factory import create_superuser, create_user

PERMISSION = "security.view_auditlog"
OTHER_PERMISSION = "security.add_auditlog"
ROLE = "auditors"


def build_view(*permissions):
    class ProtectedView(APIView):
        permission_classes = permissions

        def get(self, request):
            return Response({"ok": True})

    return ProtectedView.as_view()


def call(view, user=None):
    request = APIRequestFactory().get("/api/v1/protected/")
    if user is not None:
        force_authenticate(request, user=user)
    response = view(request)
    response.render()
    return response


class PermissionTestCase(TestCase):
    def setUp(self):
        self.permission = Permission.objects.get(codename="view_auditlog")
        self.role = Group.objects.create(name=ROLE)
        self.role.permissions.add(self.permission)

    def assertStatus(self, view, user, expected):
        self.assertEqual(call(view, user).status_code, expected)

    def user_with_role(self):
        user = create_user(email="role@example.com")
        user.groups.add(self.role)
        return user


class HasPermissionTests(PermissionTestCase):
    view = staticmethod(build_view(HasPermission(PERMISSION)))

    def test_anonymous_is_unauthorized(self):
        response = call(self.view)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "not_authenticated")

    def test_user_without_the_permission_is_forbidden(self):
        response = call(self.view, create_user())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "permission_denied")

    def test_user_with_the_permission_passes(self):
        user = create_user()
        user.user_permissions.add(self.permission)

        self.assertStatus(self.view, user, status.HTTP_200_OK)

    def test_permission_through_a_role_passes(self):
        self.assertStatus(self.view, self.user_with_role(), status.HTTP_200_OK)

    def test_superuser_passes(self):
        self.assertStatus(self.view, create_superuser(), status.HTTP_200_OK)


class HasRoleTests(PermissionTestCase):
    view = staticmethod(build_view(HasRole(ROLE)))

    def test_anonymous_is_unauthorized(self):
        self.assertStatus(self.view, None, status.HTTP_401_UNAUTHORIZED)

    def test_user_without_the_role_is_forbidden(self):
        self.assertStatus(self.view, create_user(), status.HTTP_403_FORBIDDEN)

    def test_user_with_the_role_passes(self):
        self.assertStatus(self.view, self.user_with_role(), status.HTTP_200_OK)

    def test_superuser_passes(self):
        self.assertStatus(self.view, create_superuser(), status.HTTP_200_OK)

    def test_another_role_does_not_count(self):
        user = create_user()
        user.groups.add(Group.objects.create(name="billing"))

        self.assertStatus(self.view, user, status.HTTP_403_FORBIDDEN)


class PermissionCompositionTests(PermissionTestCase):
    def test_or_passes_with_either_side(self):
        view = build_view(HasRole(ROLE) | HasPermission(OTHER_PERMISSION))
        user = create_user()
        user.user_permissions.add(Permission.objects.get(codename="add_auditlog"))

        self.assertStatus(view, self.user_with_role(), status.HTTP_200_OK)
        self.assertStatus(view, user, status.HTTP_200_OK)

    def test_and_needs_both_sides(self):
        view = build_view(HasRole(ROLE) & HasPermission(OTHER_PERMISSION))

        self.assertStatus(view, self.user_with_role(), status.HTTP_403_FORBIDDEN)

    def test_combines_with_drf_permissions(self):
        view = build_view(IsAuthenticated & ~HasRole(ROLE))

        self.assertStatus(view, create_user(), status.HTTP_200_OK)
        self.assertStatus(view, self.user_with_role(), status.HTTP_403_FORBIDDEN)

    def test_negation_also_holds_for_objects(self):
        request = APIRequestFactory().get("/api/v1/protected/")
        request.user = create_user()
        permission = (~HasRole(ROLE))()

        self.assertTrue(permission.has_object_permission(request, None, object()))


class PermissionCodenameTests(SimpleTestCase):
    def test_codename_without_app_label_fails_when_declared(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "app_label.codename"):
            HasPermission("view_auditlog")

from io import StringIO

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils.module_loading import import_string
from rest_framework import status

from security.permissions import HasPermission, HasRole

from .test_permissions import build_view, call
from .user_factory import create_user

DECLARATIONS = "security.tests.role_declarations"


def run_sync(declaration, *arguments):
    output, errors = StringIO(), StringIO()
    with override_settings(ROLE_DEFINITIONS=f"{DECLARATIONS}.{declaration}"):
        call_command("sync_roles", *arguments, stdout=output, stderr=errors)
    return output.getvalue(), errors.getvalue()


def role_permissions():
    groups = Group.objects.prefetch_related("permissions__content_type")
    return {
        group.name: sorted(
            f"{permission.content_type.app_label}.{permission.codename}"
            for permission in group.permissions.all()
        )
        for group in groups
    }


class DefaultDeclarationTests(SimpleTestCase):
    def test_the_base_declares_no_roles(self):
        self.assertEqual(settings.ROLE_DEFINITIONS, "core.roles.ROLES")
        self.assertEqual(import_string(settings.ROLE_DEFINITIONS), {})


class SyncRolesTests(TestCase):
    def test_no_roles_declared_says_so(self):
        output, _ = run_sync("NO_ROLES")

        self.assertIn("No roles declared", output)
        self.assertFalse(Group.objects.exists())

    def test_creates_the_declared_roles_with_their_permissions(self):
        output, _ = run_sync("TWO_ROLES")

        self.assertEqual(
            role_permissions(),
            {
                "auditors": ["security.view_auditlog"],
                "support": ["security.change_user", "security.view_user"],
            },
        )
        self.assertIn('Role "auditors": create, add security.view_auditlog', output)
        self.assertIn(
            "Roles synced: 2 created, 3 permissions added, 0 removed.", output
        )

    def test_second_run_changes_nothing(self):
        run_sync("TWO_ROLES")
        before = role_permissions()

        with CaptureQueriesContext(connection) as queries:
            output, _ = run_sync("TWO_ROLES")

        self.assertEqual(role_permissions(), before)
        self.assertEqual(Group.objects.count(), 2)
        self.assertIn("Roles already in sync.", output)
        writes = [query for query in queries if not query["sql"].startswith("SELECT")]
        self.assertEqual(writes, [])

    def test_removes_a_permission_dropped_from_the_declaration(self):
        run_sync("TWO_ROLES")

        output, _ = run_sync("SUPPORT_WITHOUT_CHANGE")

        self.assertEqual(role_permissions()["support"], ["security.view_user"])
        self.assertIn('Role "support": remove security.change_user', output)
        self.assertIn("0 created, 0 permissions added, 1 removed.", output)

    def test_completes_a_group_created_by_hand(self):
        Group.objects.create(name="support")

        run_sync("TWO_ROLES")

        self.assertEqual(Group.objects.filter(name="support").count(), 1)
        self.assertEqual(
            role_permissions()["support"],
            ["security.change_user", "security.view_user"],
        )

    def test_dry_run_shows_the_plan_and_writes_nothing(self):
        Group.objects.create(name="support")

        output, _ = run_sync("TWO_ROLES", "--dry-run")

        self.assertEqual(role_permissions(), {"support": []})
        self.assertIn('Role "auditors": create, add security.view_auditlog', output)
        self.assertIn(
            'Role "support": add security.change_user, security.view_user', output
        )
        self.assertIn("Dry run: nothing was changed.", output)

    def test_role_without_permissions_is_created_empty(self):
        run_sync("ROLE_WITHOUT_PERMISSIONS")

        self.assertEqual(role_permissions(), {"guests": []})

    def test_queries_do_not_grow_with_the_permissions(self):
        with CaptureQueriesContext(connection) as one:
            run_sync("ONE_PERMISSION")
        Group.objects.all().delete()
        with CaptureQueriesContext(connection) as five:
            run_sync("FIVE_PERMISSIONS")

        self.assertEqual(len(five), len(one))


class SyncRolesWarningTests(TestCase):
    def test_missing_permission_is_reported_and_the_rest_applied(self):
        output, errors = run_sync("WITH_MISSING_PERMISSION")

        self.assertEqual(role_permissions(), {"reports": ["security.view_auditlog"]})
        self.assertIn(
            'role "reports" declares billing.export_invoice, which does not exist',
            errors,
        )
        self.assertIn("Roles synced: 1 created", output)

    def test_undeclared_group_is_left_as_is_and_reported(self):
        legacy = Group.objects.create(name="legacy")

        output, _ = run_sync("TWO_ROLES")

        self.assertTrue(Group.objects.filter(pk=legacy.pk).exists())
        self.assertIn(
            'Group "legacy" exists in the database but is not declared', output
        )


class SyncRolesDeclarationErrorTests(TestCase):
    def test_permission_without_app_label_stops_before_writing(self):
        message = 'Role "broken": "view_auditlog" needs the form app_label.codename'

        with self.assertRaisesMessage(CommandError, message):
            run_sync("WITHOUT_APP_LABEL")
        self.assertFalse(Group.objects.exists())

    def test_permissions_must_be_a_list(self):
        with self.assertRaisesMessage(CommandError, 'Role "auditors"'):
            run_sync("PERMISSIONS_NOT_IN_A_LIST")

    def test_unknown_declaration_path_is_reported(self):
        with self.assertRaisesMessage(CommandError, "MISSING_DECLARATION"):
            run_sync("MISSING_DECLARATION")


class SyncedRolePermissionTests(TestCase):
    def test_a_member_of_a_synced_role_passes_has_role_and_has_permission(self):
        run_sync("TWO_ROLES")
        user = create_user()
        user.groups.add(Group.objects.get(name="auditors"))

        for permission in (
            HasRole("auditors"),
            HasPermission("security.view_auditlog"),
        ):
            with self.subTest(permission=permission):
                response = call(build_view(permission), user)

                self.assertEqual(response.status_code, status.HTTP_200_OK)

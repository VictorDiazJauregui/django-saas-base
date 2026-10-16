import uuid

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from security.models import AuditLog

from .user_factory import DEFAULT_PASSWORD, create_superuser, create_user

User = get_user_model()


class AdminTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = create_superuser()

    def setUp(self):
        self.client.force_login(self.superuser)


class UserAdminTests(AdminTestCase):
    def test_user_model_is_registered(self):
        self.assertTrue(admin.site.is_registered(User))

    def test_lists_users_by_email(self):
        response = self.client.get(reverse("admin:security_user_changelist"))

        self.assertContains(response, self.superuser.email)

    def test_creates_user_with_usable_password(self):
        form_data = {
            "email": "new.member@example.com",
            "password1": DEFAULT_PASSWORD,
            "password2": DEFAULT_PASSWORD,
        }

        self.client.post(reverse("admin:security_user_add"), form_data)

        created_user = User.objects.get(email="new.member@example.com")
        self.assertTrue(created_user.check_password(DEFAULT_PASSWORD))

    def test_opens_user_change_form(self):
        user = create_user()

        response = self.client.get(
            reverse("admin:security_user_change", args=[user.pk])
        )

        self.assertContains(response, user.email)

    def test_changes_password_from_the_user_uuid_url(self):
        user = create_user()
        new_password = "An0ther-Passphrase-42"
        form_data = {"password1": new_password, "password2": new_password}

        self.client.post(
            reverse("admin:auth_user_password_change", args=[user.pk]), form_data
        )

        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))

    def test_redirects_when_the_user_uuid_does_not_exist(self):
        response = self.client.get(
            reverse("admin:security_user_change", args=[uuid.uuid4()])
        )

        self.assertRedirects(response, reverse("admin:index"))


class AuditLogAdminTests(AdminTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.entry = AuditLog.objects.create(
            method="POST", path="/api/v1/auth/register/", payload={"email": "a@b.co"}
        )

    def test_lists_audit_entries(self):
        response = self.client.get(reverse("admin:security_auditlog_changelist"))

        self.assertContains(response, self.entry.path)

    def test_shows_payload_in_detail(self):
        response = self.client.get(
            reverse("admin:security_auditlog_change", args=[self.entry.pk])
        )

        self.assertContains(response, "a@b.co")


class ReadOnlyAuditLogAdminTests(AdminTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.entry = AuditLog.objects.create(
            method="POST", path="/api/v1/auth/login/", payload={"email": "a@b.co"}
        )

    def change_url(self):
        return reverse("admin:security_auditlog_change", args=[self.entry.pk])

    def delete_url(self):
        return reverse("admin:security_auditlog_delete", args=[self.entry.pk])

    def test_add_form_is_forbidden(self):
        response = self.client.get(reverse("admin:security_auditlog_add"))

        self.assertEqual(response.status_code, 403)

    def test_add_submit_is_forbidden_and_creates_nothing(self):
        response = self.client.post(reverse("admin:security_auditlog_add"), {})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(AuditLog.objects.filter(method="").exists())

    def test_change_submit_is_forbidden(self):
        response = self.client.post(self.change_url(), {"_save": "Save"})

        self.assertEqual(response.status_code, 403)

    def test_delete_confirmation_is_forbidden(self):
        response = self.client.get(self.delete_url())

        self.assertEqual(response.status_code, 403)

    def test_delete_submit_is_forbidden_and_keeps_the_entry(self):
        response = self.client.post(self.delete_url(), {"post": "yes"})

        self.assertEqual(response.status_code, 403)
        self.assertTrue(AuditLog.objects.filter(pk=self.entry.pk).exists())

    def test_bulk_delete_action_is_not_offered(self):
        request = RequestFactory().get(reverse("admin:security_auditlog_changelist"))
        request.user = self.superuser

        actions = admin.site.get_model_admin(AuditLog).get_actions(request)

        self.assertNotIn("delete_selected", actions)

    def test_list_has_no_add_link(self):
        response = self.client.get(reverse("admin:security_auditlog_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("admin:security_auditlog_add"))

    def test_detail_is_shown_without_save_or_delete(self):
        response = self.client.get(self.change_url())

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_save"')
        self.assertNotContains(response, self.delete_url())


class AuditLogAdminPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.entry = AuditLog.objects.create(method="POST", path="/api/v1/x/")
        cls.staff = create_user(email="staff@example.com")
        cls.staff.is_staff = True
        cls.staff.save()

    def grant_view_permission(self):
        permission = Permission.objects.get(codename="view_auditlog")
        self.staff.user_permissions.add(permission)

    def test_staff_without_permission_cannot_list(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("admin:security_auditlog_changelist"))

        self.assertEqual(response.status_code, 403)

    def test_staff_with_view_permission_can_list_and_open(self):
        self.grant_view_permission()
        self.client.force_login(self.staff)
        change_url = reverse("admin:security_auditlog_change", args=[self.entry.pk])

        list_response = self.client.get(reverse("admin:security_auditlog_changelist"))
        detail_response = self.client.get(change_url)

        self.assertEqual(
            [list_response.status_code, detail_response.status_code], [200, 200]
        )

    def test_staff_with_view_permission_cannot_delete(self):
        self.grant_view_permission()
        self.client.force_login(self.staff)
        delete_url = reverse("admin:security_auditlog_delete", args=[self.entry.pk])

        response = self.client.post(delete_url, {"post": "yes"})

        self.assertEqual(response.status_code, 403)


class AuditLogStatusAdminTests(AdminTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for status_code in (200, 201, 401, 429, 500, None):
            AuditLog.objects.create(
                method="POST", path=f"/status/{status_code}/", status_code=status_code
            )

    def listed_paths(self, **filters):
        response = self.client.get(
            reverse("admin:security_auditlog_changelist"), filters
        )
        return sorted(entry.path for entry in response.context["cl"].result_list)

    def test_lists_the_status_code_column(self):
        response = self.client.get(reverse("admin:security_auditlog_changelist"))

        self.assertContains(response, "column-status_code")

    def test_filters_by_status_class(self):
        self.assertEqual(
            self.listed_paths(status_class="4xx"), ["/status/401/", "/status/429/"]
        )

    def test_filters_entries_without_status(self):
        self.assertEqual(self.listed_paths(status_class="none"), ["/status/None/"])

    def test_ignores_an_unknown_status_class(self):
        self.assertEqual(len(self.listed_paths(status_class="9xx")), 6)

    def test_shows_the_status_code_in_detail(self):
        entry = AuditLog.objects.get(status_code=429)

        response = self.client.get(
            reverse("admin:security_auditlog_change", args=[entry.pk])
        )

        self.assertContains(response, "field-status_code")


class AuditedAdminFormTests(TestCase):
    def test_user_added_from_the_admin_is_audited_with_passwords_redacted(self):
        self.client.force_login(create_superuser())
        fields = {
            "csrfmiddlewaretoken": "token-sent-by-the-form",
            "email": "added@example.com",
            "usable_password": "true",
            "password1": DEFAULT_PASSWORD,
            "password2": DEFAULT_PASSWORD,
            "_save": "Save",
        }

        self.client.post(reverse("admin:security_user_add"), fields)

        stored = AuditLog.objects.get(path=reverse("admin:security_user_add")).payload
        self.assertEqual(stored["email"], "added@example.com")
        self.assertEqual([stored["password1"], stored["password2"]], ["[REDACTED]"] * 2)
        self.assertNotIn("csrfmiddlewaretoken", stored)

    def test_failed_admin_login_is_audited_with_the_email(self):
        fields = {
            "csrfmiddlewaretoken": "token-sent-by-the-form",
            "username": "intruder@example.com",
            "password": "Wrong-Passphrase-1",
        }

        response = self.client.post(reverse("admin:login"), fields)

        entry = AuditLog.objects.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            entry.payload,
            {"username": "intruder@example.com", "password": "[REDACTED]"},
        )


class AuditLogListAdminTests(AdminTestCase):
    def create_entries(self, count, offset=0):
        for number in range(offset, offset + count):
            user = create_user(email=f"listed{number}@example.com")
            AuditLog.objects.create(
                user=user, method="POST", path="/listed/", payload={"note": "needle"}
            )

    def count_list_queries(self):
        with CaptureQueriesContext(connection) as queries:
            self.client.get(reverse("admin:security_auditlog_changelist"))
        return len(queries.captured_queries)

    def test_list_runs_the_same_queries_with_5_or_50_entries(self):
        self.create_entries(5)
        queries_with_5 = self.count_list_queries()
        self.create_entries(45, offset=5)

        self.assertEqual(self.count_list_queries(), queries_with_5)

    def test_does_not_offer_a_filter_by_user(self):
        self.create_entries(2)

        response = self.client.get(reverse("admin:security_auditlog_changelist"))

        self.assertNotContains(response, "user__id__exact")

    def test_search_finds_by_email_but_not_inside_the_payload(self):
        self.create_entries(1)
        list_url = reverse("admin:security_auditlog_changelist")

        by_payload = self.client.get(list_url, {"q": "needle"})
        by_email = self.client.get(list_url, {"q": "listed0@example.com"})

        self.assertEqual(len(by_payload.context["cl"].result_list), 0)
        self.assertEqual(len(by_email.context["cl"].result_list), 1)

    def test_does_not_count_every_entry_when_searching(self):
        self.create_entries(3)

        response = self.client.get(
            reverse("admin:security_auditlog_changelist"), {"q": "listed1"}
        )

        self.assertNotContains(response, "3 total")

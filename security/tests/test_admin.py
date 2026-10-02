from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
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

from django.test import TestCase
from django.urls import reverse

from organizations.models import OrganizationApiKey
from security.models import AuditLog
from security.tests.user_factory import create_superuser

from .organization_factory import create_organization, create_organization_api_key

CHANGELIST = "admin:organizations_organizationapikey_changelist"
ADD = "admin:organizations_organizationapikey_add"


class OrganizationApiKeyAdminTests(TestCase):
    def setUp(self):
        self.staff = create_superuser()
        self.client.force_login(self.staff)
        self.organization = create_organization("Acme")

    def test_the_list_shows_the_organization_and_finds_by_prefix(self):
        api_key, _ = create_organization_api_key(self.organization)
        create_organization_api_key(create_organization("Globex"), name="Other")
        response = self.client.get(reverse(CHANGELIST), {"q": api_key.prefix})
        self.assertContains(response, api_key.prefix)
        self.assertContains(response, "Acme")
        self.assertNotContains(response, "Globex")

    def test_adding_shows_the_key_once_and_stores_only_its_hash(self):
        form_data = {
            "organization": self.organization.pk,
            "name": "ERP",
            "role": "member",
        }
        response = self.client.post(reverse(ADD), form_data)
        api_key = OrganizationApiKey.objects.get()
        raw_key = response.context["raw_key"]
        self.assertContains(response, raw_key)
        self.assertTrue(raw_key.startswith(f"{api_key.prefix}."))
        self.assertIn("no-cache", response["Cache-Control"])
        self.assertEqual(api_key.created_by, self.staff)

    def test_the_owner_role_is_not_offered(self):
        form = self.client.get(reverse(ADD)).context["adminform"].form
        self.assertEqual(
            [value for value, _ in form.fields["role"].choices], ["admin", "member"]
        )

    def test_the_revoke_action_marks_the_selected_keys(self):
        api_key, _ = create_organization_api_key(self.organization)
        form_data = {"action": "revoke_selected", "_selected_action": [api_key.pk]}
        self.client.post(reverse(CHANGELIST), form_data)
        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.revoked_at)

    def test_a_key_is_never_edited(self):
        api_key, _ = create_organization_api_key(self.organization)
        url = reverse(
            "admin:organizations_organizationapikey_change", args=[api_key.pk]
        )
        self.assertNotContains(self.client.get(url), 'name="_save"')

    def test_the_audit_log_admin_finds_the_actions_of_a_key_by_prefix(self):
        AuditLog.objects.create(
            method="POST",
            path="/api/v1/organizations/acme/projects/",
            api_key_prefix="org_0123456789ab",
            organization_id=self.organization.pk,
        )
        changelist = reverse("admin:security_auditlog_changelist")
        response = self.client.get(changelist, {"q": "org_0123456789ab"})
        self.assertContains(response, "/api/v1/organizations/acme/projects/")

from django.test import TestCase
from django.urls import reverse

from organizations.models import Organization
from security.tests.user_factory import create_superuser, create_user

from .organization_factory import add_member, create_member, create_organization

INLINE_PREFIX = "memberships"


def build_organization_form(name, members):
    form_data = {
        "name": name,
        "slug": "",
        f"{INLINE_PREFIX}-TOTAL_FORMS": str(len(members)),
        f"{INLINE_PREFIX}-INITIAL_FORMS": "0",
    }
    for index, (user, role) in enumerate(members):
        form_data[f"{INLINE_PREFIX}-{index}-user"] = str(user.pk)
        form_data[f"{INLINE_PREFIX}-{index}-role"] = role
    return form_data


class OrganizationAdminTests(TestCase):
    def setUp(self):
        self.client.force_login(create_superuser())

    def test_the_list_shows_slug_and_member_count(self):
        organization = create_organization("Acme")
        create_member(organization, "one@example.com")
        create_member(organization, "two@example.com", "owner")
        response = self.client.get(
            reverse("admin:organizations_organization_changelist")
        )
        self.assertContains(response, "acme")
        self.assertContains(
            response, '<td class="field-member_count">2</td>', html=True
        )

    def test_creating_an_organization_with_its_owner(self):
        owner = create_user("owner@example.com")
        form_data = build_organization_form("Acme Corp", [(owner, "owner")])
        response = self.client.post(
            reverse("admin:organizations_organization_add"), form_data
        )
        self.assertEqual(response.status_code, 302)
        organization = Organization.objects.get()
        self.assertEqual(organization.slug, "acme-corp")
        self.assertEqual(organization.memberships.get().user, owner)

    def test_the_delete_confirmation_lists_the_memberships(self):
        organization = create_organization("Acme")
        create_member(organization, "member@example.com")
        url = reverse("admin:organizations_organization_delete", args=[organization.pk])
        response = self.client.get(url)
        self.assertContains(response, "member@example.com")

    def test_the_search_finds_by_name_and_slug(self):
        create_organization("Acme")
        create_organization("Globex")
        url = reverse("admin:organizations_organization_changelist")
        response = self.client.get(url, {"q": "glob"})
        self.assertContains(response, "Globex")
        self.assertNotContains(response, "Acme")


class UserMembershipInlineTests(TestCase):
    def setUp(self):
        self.client.force_login(create_superuser())
        self.user = create_user()
        add_member(create_organization("Acme"), self.user, "admin")

    def test_the_user_page_lists_the_organizations_read_only(self):
        url = reverse("admin:security_user_change", args=[self.user.pk])
        response = self.client.get(url)
        self.assertContains(response, "Acme")
        self.assertNotContains(response, 'name="memberships-0-role"')

    def test_the_add_user_page_has_no_inline(self):
        response = self.client.get(reverse("admin:security_user_add"))
        self.assertNotContains(response, "memberships-TOTAL_FORMS")

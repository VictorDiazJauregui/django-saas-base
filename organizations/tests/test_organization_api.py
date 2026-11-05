import uuid

from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from organizations.models import Membership, Organization
from security.models import AuditLog
from security.tests.api_test_case import CacheResetAPITestCase
from security.tests.user_factory import create_user

from .organization_factory import add_member, create_organization


def organization_url(organization_id):
    return reverse("organizations:detail", kwargs={"organization_id": organization_id})


@override_settings(TENANCY_ENABLED=True)
class OrganizationApiTestCase(CacheResetAPITestCase):
    list_url = reverse("organizations:list")

    def setUp(self):
        super().setUp()
        self.user = create_user()
        self.client.force_authenticate(self.user)

    def assert_error(self, response, status_code, code):
        self.assertEqual(response.status_code, status_code, response.content)
        self.assertEqual(response.json()["code"], code)


class OrganizationListTests(OrganizationApiTestCase):
    def test_lists_only_the_organizations_of_the_user_with_their_role(self):
        add_member(create_organization("Acme"), self.user, "admin")
        add_member(create_organization("Globex"), self.user, "member")
        create_organization("Initech")
        results = self.client.get(self.list_url).json()["results"]
        self.assertEqual(
            [(item["name"], item["role"]) for item in results],
            [("Acme", "admin"), ("Globex", "member")],
        )

    def test_each_item_has_the_documented_fields(self):
        add_member(create_organization("Acme"), self.user, "owner")
        item = self.client.get(self.list_url).json()["results"][0]
        self.assertEqual(set(item), {"id", "name", "slug", "role", "created_at"})

    def test_without_a_token_asks_for_credentials(self):
        self.client.force_authenticate(None)
        response = self.client.get(self.list_url)
        self.assert_error(response, status.HTTP_401_UNAUTHORIZED, "not_authenticated")

    @override_settings(TENANCY_ENABLED=False)
    def test_with_the_module_off_the_route_does_not_exist(self):
        self.assert_error(self.client.get(self.list_url), 404, "not_found")
        self.client.force_authenticate(None)
        self.assert_error(self.client.post(self.list_url, {}), 404, "not_found")


class OrganizationCreateTests(OrganizationApiTestCase):
    def create(self, payload):
        return self.client.post(self.list_url, payload, format="json")

    def test_the_creator_becomes_the_owner(self):
        response = self.create({"name": "Acme Corp"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["slug"], "acme-corp")
        self.assertEqual(response.json()["role"], "owner")
        membership = Membership.objects.get()
        self.assertEqual((membership.user, membership.role), (self.user, "owner"))

    def test_a_given_slug_is_kept(self):
        response = self.create({"name": "Acme Corp", "slug": "acme"})
        self.assertEqual(response.json()["slug"], "acme")

    def test_a_taken_slug_is_a_field_error(self):
        create_organization("Acme")
        response = self.create({"name": "Other", "slug": "acme"})
        self.assert_error(response, status.HTTP_400_BAD_REQUEST, "invalid")
        self.assertIn("slug", response.json()["fields"])

    def test_the_name_is_required_and_short(self):
        for name in ("", "x" * 101):
            with self.subTest(length=len(name)):
                response = self.create({"name": name})
                self.assertIn("name", response.json()["fields"])
        self.assertFalse(Organization.objects.exists())

    def test_the_creation_is_audited_with_its_path(self):
        self.create({"name": "Acme"})
        audit = AuditLog.objects.get(path=self.list_url)
        self.assertEqual((audit.user, audit.status_code), (self.user, 201))


class OrganizationDetailTests(OrganizationApiTestCase):
    def setUp(self):
        super().setUp()
        self.organization = create_organization("Acme")
        self.url = organization_url(self.organization.pk)

    def test_a_member_reads_it_with_their_role(self):
        add_member(self.organization, self.user, "member")
        response = self.client.get(self.url)
        self.assertEqual(response.json()["role"], "member")
        self.assertEqual(response.json()["id"], str(self.organization.pk))

    def test_someone_else_gets_not_found(self):
        response = self.client.get(self.url)
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "organization_not_found")

    def test_an_unknown_id_gets_not_found(self):
        add_member(self.organization, self.user, "owner")
        response = self.client.get(organization_url(uuid.uuid4()))
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "organization_not_found")

    def test_an_admin_renames_it(self):
        add_member(self.organization, self.user, "admin")
        payload = {"name": "Acme Holdings", "slug": "acme-holdings"}
        response = self.client.patch(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.slug, "acme-holdings")
        self.assertEqual(response.json()["role"], "admin")

    def test_a_member_cannot_change_it(self):
        add_member(self.organization, self.user, "member")
        response = self.client.patch(self.url, {"name": "Mine"}, format="json")
        self.assert_error(response, status.HTTP_403_FORBIDDEN, "permission_denied")

    def test_the_slug_of_another_organization_is_a_field_error(self):
        create_organization("Globex")
        add_member(self.organization, self.user, "owner")
        response = self.client.patch(self.url, {"slug": "globex"}, format="json")
        self.assertIn("slug", response.json()["fields"])

    def test_organizations_are_not_deleted_through_the_api(self):
        add_member(self.organization, self.user, "owner")
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Organization.objects.filter(pk=self.organization.pk).exists())

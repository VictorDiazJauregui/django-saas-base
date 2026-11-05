import uuid

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status

from organizations.models import Organization
from security.models import AuditLog
from security.tests.api_test_case import CacheResetAPITestCase
from security.tests.user_factory import create_superuser, create_user

from .organization_factory import add_member, create_organization
from .scoped_project import Project, create_project_table
from .test_admin import build_organization_form
from .test_permissions import TEST_URLS

UUID_SHAPED_SLUGS = (
    "123e4567-e89b-12d3-a456-426614174000",
    "123e4567e89b12d3a456426614174000",
)


def detail_url(organization_reference: object) -> str:
    return reverse(
        "organizations:detail", kwargs={"organization_id": organization_reference}
    )


@override_settings(TENANCY_ENABLED=True)
class OrganizationReferenceTestCase(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user()
        self.organization = create_organization("Acme")
        add_member(self.organization, self.user, "admin")
        self.client.force_authenticate(self.user)

    def assert_error(self, response, status_code: int, code: str) -> None:
        self.assertEqual(response.status_code, status_code, response.content)
        self.assertEqual(response.json()["code"], code)


class SlugRouteTests(OrganizationReferenceTestCase):
    def test_reading_by_slug_answers_as_by_id(self):
        by_slug = self.client.get(detail_url("acme"))
        by_id = self.client.get(detail_url(self.organization.pk))
        self.assertEqual(by_slug.status_code, status.HTTP_200_OK)
        self.assertEqual(by_slug.json(), by_id.json())

    def test_editing_by_slug_changes_the_organization(self):
        response = self.client.patch(detail_url("acme"), {"name": "Acme Inc"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, "Acme Inc")

    def test_members_and_invitations_accept_the_slug(self):
        for name in ("organizations:members", "organizations:invitations"):
            url = reverse(name, kwargs={"organization_id": "acme"})
            self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def test_the_slug_of_another_organization_answers_as_its_id(self):
        globex = create_organization("Globex")
        by_slug = self.client.get(detail_url("globex"))
        by_id = self.client.get(detail_url(globex.pk))
        self.assert_error(by_slug, status.HTTP_404_NOT_FOUND, "organization_not_found")
        self.assertEqual(by_slug.json(), by_id.json())

    def test_an_unknown_slug_is_not_found(self):
        response = self.client.get(detail_url("initech"))
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "organization_not_found")

    def test_a_malformed_reference_is_not_found(self):
        response = self.client.get("/api/v1/organizations/ac.me%20x/")
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "organization_not_found")

    def test_after_a_slug_change_only_the_new_one_works(self):
        self.client.patch(detail_url("acme"), {"slug": "acme-labs"})
        old = self.client.get(detail_url("acme"))
        self.assert_error(old, status.HTTP_404_NOT_FOUND, "organization_not_found")
        self.assertEqual(
            self.client.get(detail_url("acme-labs")).status_code, status.HTTP_200_OK
        )

    @override_settings(TENANCY_ENABLED=False)
    def test_with_the_module_off_the_slug_route_does_not_exist(self):
        self.assert_error(self.client.get(detail_url("acme")), 404, "not_found")

    def test_reverse_with_a_uuid_keeps_the_same_path(self):
        organization_id = uuid.uuid4()
        expected = f"/api/v1/organizations/{organization_id}/"
        self.assertEqual(detail_url(organization_id), expected)

    def test_the_audit_log_keeps_the_path_as_it_came(self):
        self.client.patch(detail_url("acme"), {"name": "Acme Inc"})
        self.assertEqual(AuditLog.objects.get().path, "/api/v1/organizations/acme/")


class SlugValidationTests(OrganizationReferenceTestCase):
    list_url = reverse("organizations:list")

    def assert_slug_error(self, response) -> None:
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("slug", response.json()["fields"])

    def test_a_uuid_shaped_slug_is_refused_on_creation(self):
        for slug in UUID_SHAPED_SLUGS:
            with self.subTest(slug=slug):
                response = self.client.post(self.list_url, {"name": "X", "slug": slug})
                self.assert_slug_error(response)

    def test_a_uuid_shaped_slug_is_refused_on_edition(self):
        for slug in UUID_SHAPED_SLUGS:
            with self.subTest(slug=slug):
                self.assert_slug_error(
                    self.client.patch(detail_url("acme"), {"slug": slug})
                )

    def test_an_uppercase_slug_is_refused_on_creation_and_edition(self):
        created = self.client.post(self.list_url, {"name": "X", "slug": "Acme-Two"})
        edited = self.client.patch(detail_url("acme"), {"slug": "ACME"})
        self.assert_slug_error(created)
        self.assert_slug_error(edited)

    def test_a_name_shaped_like_a_uuid_gets_the_default_slug(self):
        organization = Organization.objects.create(name=UUID_SHAPED_SLUGS[0])
        self.assertEqual(organization.slug, "organization")


class SlugAdminValidationTests(TestCase):
    def test_the_admin_form_refuses_a_uuid_shaped_slug(self):
        self.client.force_login(create_superuser())
        form_data = {
            **build_organization_form("Acme", []),
            "slug": UUID_SHAPED_SLUGS[0],
        }
        response = self.client.post(
            reverse("admin:organizations_organization_add"), form_data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("slug", response.context["adminform"].form.errors)
        self.assertFalse(Organization.objects.exists())


@override_settings(ROOT_URLCONF=TEST_URLS, TENANCY_ENABLED=True)
class ScopedViewSetSlugTests(CacheResetAPITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_project_table()

    def setUp(self):
        super().setUp()
        self.acme, globex = create_organization("Acme"), create_organization("Globex")
        Project.objects.create(organization=self.acme, name="Rocket")
        Project.objects.create(organization=globex, name="Secret")
        user = create_user()
        add_member(self.acme, user)
        self.client.force_authenticate(user)

    def list_projects(self, organization_reference: str):
        url = reverse(
            "project-list", kwargs={"organization_id": organization_reference}
        )
        return self.client.get(url)

    def test_the_list_by_slug_shows_only_the_organization_rows(self):
        names = [row["name"] for row in self.list_projects("acme").json()["results"]]
        self.assertEqual(names, ["Rocket"])

    def test_the_list_of_another_organization_by_slug_is_not_found(self):
        response = self.list_projects("globex")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["code"], "organization_not_found")

    def test_the_slug_is_resolved_with_a_single_query(self):
        url = reverse("echo", kwargs={"organization_id": "acme"})
        with self.assertNumQueries(1):
            self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

from django.db import models
from django.test import override_settings
from django.urls import include, path, reverse
from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.test import APITestCase

from organizations.models import OrganizationScopedModel
from security.tests.user_factory import create_user

from .organization_factory import add_member, create_organization
from .scoped_project import Project, ProjectViewSet, create_project_table
from .test_permissions import TEST_URLS
from .urls_scoped_views import ORGANIZATION_PREFIX, router


# A member of Acme tries every action against Globex's rows: none of them may get through.
@override_settings(ROOT_URLCONF=TEST_URLS, TENANCY_ENABLED=True)
class OrganizationIsolationTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_project_table()

    def setUp(self):
        self.acme, self.globex = create_organization("Acme"), create_organization(
            "Globex"
        )
        self.acme_project = Project.objects.create(
            organization=self.acme, name="Rocket"
        )
        self.globex_project = Project.objects.create(
            organization=self.globex, name="Secret"
        )
        self.user = create_user()
        add_member(self.acme, self.user)
        self.client.force_authenticate(self.user)

    def list_url(self, organization):
        return reverse("project-list", kwargs={"organization_id": organization.pk})

    def detail_url(self, organization, project):
        kwargs = {"organization_id": organization.pk, "pk": project.pk}
        return reverse("project-detail", kwargs=kwargs)

    def test_the_list_shows_only_the_organization_rows(self):
        response = self.client.get(self.list_url(self.acme))
        names = [project["name"] for project in response.json()["results"]]
        self.assertEqual(names, ["Rocket"])

    def test_another_organization_list_is_not_found(self):
        response = self.client.get(self.list_url(self.globex))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_row_of_another_organization_is_not_found_through_your_own(self):
        response = self.client.get(self.detail_url(self.acme, self.globex_project))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["code"], "not_found")

    def test_a_row_of_another_organization_cannot_be_changed(self):
        url = self.detail_url(self.acme, self.globex_project)
        response = self.client.patch(url, {"name": "Stolen"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.globex_project.refresh_from_db()
        self.assertEqual(self.globex_project.name, "Secret")

    def test_a_row_of_another_organization_cannot_be_deleted(self):
        response = self.client.delete(self.detail_url(self.acme, self.globex_project))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Project.objects.filter(pk=self.globex_project.pk).exists())

    def test_creating_in_another_organization_is_not_found(self):
        response = self.client.post(
            self.list_url(self.globex), {"name": "X"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Project.objects.filter(organization=self.globex).count(), 1)

    def test_creating_assigns_the_organization_of_the_url(self):
        payload = {"name": "Probe", "organization": str(self.globex.pk)}
        response = self.client.post(self.list_url(self.acme), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["organization"], str(self.acme.pk))

    def test_an_update_cannot_move_a_row_to_another_organization(self):
        url = self.detail_url(self.acme, self.acme_project)
        payload = {"name": "Moved", "organization": str(self.globex.pk)}
        response = self.client.patch(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.acme_project.refresh_from_db()
        self.assertEqual(self.acme_project.organization, self.acme)

    def test_a_member_works_on_the_organization_rows(self):
        url = self.detail_url(self.acme, self.acme_project)
        response = self.client.patch(url, {"name": "Rocket 2"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT
        )


class OrganizationScopedModelTests(APITestCase):
    def test_the_rows_go_with_their_organization(self):
        field = OrganizationScopedModel._meta.get_field("organization")
        self.assertEqual(field.remote_field.on_delete, models.CASCADE)
        self.assertTrue(field.db_index)
        self.assertTrue(OrganizationScopedModel._meta.abstract)


class OrganizationScopedSchemaTests(APITestCase):
    def test_the_schema_generator_gets_an_empty_queryset_without_a_request(self):
        view = ProjectViewSet(swagger_fake_view=True)
        self.assertFalse(view.get_queryset().exists())

    def test_the_organization_id_is_documented_as_a_uuid_path_parameter(self):
        patterns = [path(ORGANIZATION_PREFIX, include(router.urls))]
        schema = SchemaGenerator(patterns=patterns).get_schema(public=True)
        operation = schema["paths"]["/api/v1/organizations/{organization_id}/projects/"]
        parameter = operation["get"]["parameters"][0]
        self.assertEqual(parameter["name"], "organization_id")
        self.assertEqual(parameter["schema"], {"type": "string", "format": "uuid"})

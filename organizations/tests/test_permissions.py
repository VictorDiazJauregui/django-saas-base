import uuid
from types import SimpleNamespace

from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from organizations.active_organization import resolve_active_membership
from organizations.permissions import HasOrganizationRole
from security.tests.user_factory import create_superuser, create_user

from .organization_factory import add_member, create_organization

TEST_URLS = "organizations.tests.urls_scoped_views"


@override_settings(ROOT_URLCONF=TEST_URLS, TENANCY_ENABLED=True)
class OrganizationPermissionTestCase(APITestCase):
    def setUp(self):
        self.organization = create_organization("Acme")
        self.user = create_user()

    def get_view(self, name, organization_id=None):
        organization_id = organization_id or self.organization.pk
        return self.client.get(
            reverse(name, kwargs={"organization_id": organization_id})
        )

    def join(self, role):
        add_member(self.organization, self.user, role)
        self.client.force_authenticate(self.user)

    def assert_error(self, response, status_code, code):
        self.assertEqual(response.status_code, status_code, response.content)
        self.assertEqual(response.json()["code"], code)


class IsOrganizationMemberTests(OrganizationPermissionTestCase):
    def test_a_member_gets_the_organization_and_role_on_the_request(self):
        self.join("member")
        response = self.get_view("echo")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"slug": "acme", "role": "member"})

    def test_without_a_token_asks_for_credentials(self):
        response = self.get_view("echo")
        self.assert_error(response, status.HTTP_401_UNAUTHORIZED, "not_authenticated")

    def test_a_user_of_another_organization_gets_not_found(self):
        add_member(create_organization("Globex"), self.user, "owner")
        self.client.force_authenticate(self.user)
        response = self.get_view("echo")
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "organization_not_found")

    def test_an_organization_that_does_not_exist_gets_the_same_answer(self):
        self.join("owner")
        response = self.get_view("echo", uuid.uuid4())
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "organization_not_found")

    def test_a_reference_that_is_neither_an_id_nor_a_slug_gets_the_same_answer(self):
        self.join("owner")
        response = self.get_view("raw_echo", "not-an-organization")
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "organization_not_found")

    def test_a_superuser_who_is_not_a_member_gets_not_found(self):
        self.client.force_authenticate(create_superuser())
        response = self.get_view("echo")
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "organization_not_found")

    def test_a_membership_already_on_the_request_is_reused(self):
        membership = add_member(self.organization, self.user, "member")
        request = SimpleNamespace(membership=membership)
        with self.assertNumQueries(0):
            self.assertIs(resolve_active_membership(request, view=None), membership)

    def test_the_membership_is_read_once_per_request(self):
        self.join("member")
        with self.assertNumQueries(1):
            self.get_view("echo")

    @override_settings(TENANCY_ENABLED=False)
    def test_with_the_module_off_the_route_does_not_exist(self):
        self.join("owner")
        response = self.get_view("echo")
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "not_found")

    @override_settings(TENANCY_ENABLED=False)
    def test_with_the_module_off_anonymous_requests_get_not_found_too(self):
        response = self.get_view("echo")
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "not_found")


class HasOrganizationRoleTests(OrganizationPermissionTestCase):
    def test_a_member_is_denied_an_admin_route(self):
        self.join("member")
        response = self.get_view("admin_only")
        self.assert_error(response, status.HTTP_403_FORBIDDEN, "permission_denied")

    def test_an_admin_passes(self):
        self.join("admin")
        self.assertEqual(self.get_view("admin_only").status_code, status.HTTP_200_OK)

    def test_an_owner_passes_because_the_role_is_higher(self):
        self.join("owner")
        self.assertEqual(self.get_view("admin_only").status_code, status.HTTP_200_OK)

    def test_a_negated_role_lets_members_in_and_keeps_admins_out(self):
        self.join("member")
        self.assertEqual(self.get_view("non_admin").status_code, status.HTTP_200_OK)
        self.user.memberships.update(role="admin")
        response = self.get_view("non_admin")
        self.assert_error(response, status.HTTP_403_FORBIDDEN, "permission_denied")

    def test_a_negated_role_still_hides_other_organizations(self):
        self.client.force_authenticate(self.user)
        response = self.get_view("non_admin")
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "organization_not_found")

    def test_an_unknown_role_stops_at_import_time(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "'boss'"):
            HasOrganizationRole("boss")

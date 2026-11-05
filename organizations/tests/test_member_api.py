from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from organizations.models import Membership
from security.tests.api_test_case import CacheResetAPITestCase
from security.tests.user_factory import create_user

from .organization_factory import add_member, create_member, create_organization


@override_settings(TENANCY_ENABLED=True)
class MemberApiTestCase(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.organization = create_organization("Acme")
        self.user = create_user()
        self.client.force_authenticate(self.user)

    def join(self, role):
        self.membership = add_member(self.organization, self.user, role)
        return self.membership

    def members_url(self, organization=None):
        organization = organization or self.organization
        return reverse(
            "organizations:members", kwargs={"organization_id": organization.pk}
        )

    def member_url(self, membership):
        kwargs = {
            "organization_id": membership.organization_id,
            "membership_id": membership.pk,
        }
        return reverse("organizations:member", kwargs=kwargs)

    def change_role(self, membership, role):
        return self.client.patch(
            self.member_url(membership), {"role": role}, format="json"
        )

    def assert_error(self, response, status_code, code):
        self.assertEqual(response.status_code, status_code, response.content)
        self.assertEqual(response.json()["code"], code)

    def assert_role(self, membership, role):
        membership.refresh_from_db()
        self.assertEqual(membership.role, role)


class MemberListTests(MemberApiTestCase):
    def test_a_member_lists_everyone_with_their_user(self):
        self.join("member")
        create_member(self.organization, "boss@example.com", "owner")
        results = self.client.get(self.members_url()).json()["results"]
        self.assertEqual([item["role"] for item in results], ["member", "owner"])
        self.assertEqual(
            set(results[1]["user"]), {"id", "email", "first_name", "last_name"}
        )
        self.assertEqual(set(results[1]), {"id", "user", "role", "created_at"})

    def test_members_of_other_organizations_are_left_out(self):
        self.join("member")
        create_member(create_organization("Globex"), "other@example.com")
        self.assertEqual(self.client.get(self.members_url()).json()["count"], 1)

    def test_someone_else_gets_not_found(self):
        response = self.client.get(self.members_url())
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "organization_not_found")

    def test_lists_with_one_query_for_the_rows(self):
        self.join("member")
        for index in range(3):
            create_member(self.organization, f"user{index}@example.com")
        with self.assertNumQueries(3):
            self.client.get(self.members_url())


class MemberRoleChangeTests(MemberApiTestCase):
    def test_an_admin_promotes_a_member_to_admin(self):
        self.join("admin")
        member = create_member(self.organization, "member@example.com")
        response = self.change_role(member, "admin")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["role"], "admin")
        self.assert_role(member, "admin")

    def test_a_member_cannot_change_roles(self):
        self.join("member")
        other = create_member(self.organization, "other@example.com")
        response = self.change_role(other, "admin")
        self.assert_error(response, status.HTTP_403_FORBIDDEN, "permission_denied")
        self.assert_role(other, "member")

    def test_a_member_cannot_promote_themselves(self):
        self.join("member")
        response = self.change_role(self.membership, "admin")
        self.assert_error(response, status.HTTP_403_FORBIDDEN, "permission_denied")

    def test_an_admin_cannot_grant_the_owner_role(self):
        self.join("admin")
        member = create_member(self.organization, "member@example.com")
        response = self.change_role(member, "owner")
        self.assert_error(response, status.HTTP_403_FORBIDDEN, "permission_denied")

    def test_an_admin_cannot_demote_an_owner(self):
        self.join("admin")
        owner = create_member(self.organization, "owner@example.com", "owner")
        response = self.change_role(owner, "member")
        self.assert_error(response, status.HTTP_403_FORBIDDEN, "permission_denied")
        self.assert_role(owner, "owner")

    def test_an_owner_grants_the_owner_role(self):
        self.join("owner")
        admin = create_member(self.organization, "admin@example.com", "admin")
        self.assertEqual(self.change_role(admin, "owner").status_code, 200)
        self.assert_role(admin, "owner")

    def test_the_last_owner_cannot_step_down(self):
        self.join("owner")
        response = self.change_role(self.membership, "admin")
        self.assert_error(response, status.HTTP_409_CONFLICT, "last_owner")
        self.assert_role(self.membership, "owner")

    def test_an_unknown_role_is_a_field_error(self):
        self.join("owner")
        member = create_member(self.organization, "member@example.com")
        response = self.change_role(member, "boss")
        self.assertIn("role", response.json()["fields"])

    def test_a_membership_of_another_organization_is_not_found(self):
        self.join("owner")
        stranger = create_member(create_organization("Globex"), "x@example.com")
        url = reverse(
            "organizations:member",
            kwargs={
                "organization_id": self.organization.pk,
                "membership_id": stranger.pk,
            },
        )
        response = self.client.patch(url, {"role": "admin"}, format="json")
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "not_found")
        self.assert_role(stranger, "member")


class MemberRemovalTests(MemberApiTestCase):
    def remove(self, membership):
        return self.client.delete(self.member_url(membership))

    def assert_removed(self, response, membership):
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Membership.objects.filter(pk=membership.pk).exists())

    def test_an_admin_removes_a_member(self):
        self.join("admin")
        member = create_member(self.organization, "member@example.com")
        self.assert_removed(self.remove(member), member)

    def test_an_admin_cannot_remove_an_owner(self):
        self.join("admin")
        owner = create_member(self.organization, "owner@example.com", "owner")
        response = self.remove(owner)
        self.assert_error(response, status.HTTP_403_FORBIDDEN, "permission_denied")

    def test_a_member_cannot_remove_someone_else(self):
        self.join("member")
        other = create_member(self.organization, "other@example.com")
        response = self.remove(other)
        self.assert_error(response, status.HTTP_403_FORBIDDEN, "permission_denied")

    def test_a_member_leaves(self):
        self.join("member")
        self.assert_removed(self.remove(self.membership), self.membership)

    def test_an_owner_removes_another_owner(self):
        self.join("owner")
        other = create_member(self.organization, "owner2@example.com", "owner")
        self.assert_removed(self.remove(other), other)

    def test_the_last_owner_cannot_leave(self):
        self.join("owner")
        response = self.remove(self.membership)
        self.assert_error(response, status.HTTP_409_CONFLICT, "last_owner")

    def test_a_removed_user_loses_access(self):
        self.join("member")
        self.remove(self.membership)
        response = self.client.get(self.members_url())
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "organization_not_found")

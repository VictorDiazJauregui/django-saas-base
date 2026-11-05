from django.db import IntegrityError, transaction
from django.test import TestCase

from organizations.models import Membership, Organization
from organizations.roles import OrganizationRole, role_includes
from organizations.slugs import DEFAULT_SLUG, SLUG_MAX_LENGTH
from security.tests.user_factory import create_user

from .organization_factory import add_member, create_member, create_organization


class OrganizationSlugTests(TestCase):
    def test_slug_comes_from_the_name(self):
        organization = create_organization("Acme Corp")
        self.assertEqual(organization.slug, "acme-corp")

    def test_slug_drops_accents(self):
        organization = create_organization("Ñandú Café")
        self.assertEqual(organization.slug, "nandu-cafe")

    def test_name_without_latin_letters_gets_the_default_slug(self):
        organization = create_organization("株式会社")
        self.assertEqual(organization.slug, DEFAULT_SLUG)

    def test_repeated_names_get_a_numbered_slug(self):
        create_organization("Acme")
        create_organization("Acme")
        third = create_organization("Acme")
        self.assertEqual(third.slug, "acme-3")

    def test_a_given_slug_is_kept(self):
        organization = Organization.objects.create(name="Acme", slug="the-acme")
        self.assertEqual(organization.slug, "the-acme")

    def test_long_names_fit_the_slug_column_with_their_suffix(self):
        create_organization("x" * 100)
        second = create_organization("x" * 100)
        self.assertLessEqual(len(second.slug), SLUG_MAX_LENGTH)
        self.assertTrue(second.slug.endswith("-2"))

    def test_slug_is_unique(self):
        Organization.objects.create(name="Acme", slug="acme")
        with self.assertRaises(IntegrityError):
            Organization.objects.create(name="Other", slug="acme")

    def test_renaming_keeps_the_slug(self):
        organization = create_organization("Acme")
        organization.name = "Acme Holdings"
        organization.save()
        self.assertEqual(organization.slug, "acme")


class MembershipTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.organization = create_organization()

    def test_one_membership_per_user_and_organization(self):
        add_member(self.organization, self.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            add_member(self.organization, self.user, OrganizationRole.ADMIN)

    def test_a_user_can_belong_to_several_organizations(self):
        add_member(self.organization, self.user)
        add_member(create_organization("Globex"), self.user, OrganizationRole.OWNER)
        self.assertEqual(self.user.memberships.count(), 2)

    def test_deleting_the_organization_deletes_its_memberships(self):
        create_member(self.organization, "member@example.com")
        self.organization.delete()
        self.assertFalse(Membership.objects.exists())

    def test_deleting_the_user_deletes_their_memberships(self):
        add_member(self.organization, self.user)
        self.user.delete()
        self.assertFalse(Membership.objects.exists())
        self.assertTrue(Organization.objects.filter(pk=self.organization.pk).exists())

    def test_text_shows_user_role_and_organization(self):
        membership = add_member(self.organization, self.user, OrganizationRole.ADMIN)
        self.assertEqual(str(membership), f"{self.user} · Admin · Acme")


class RoleHierarchyTests(TestCase):
    def test_each_role_includes_the_ones_below(self):
        self.assertTrue(role_includes(OrganizationRole.OWNER, OrganizationRole.ADMIN))
        self.assertTrue(role_includes(OrganizationRole.ADMIN, OrganizationRole.MEMBER))
        self.assertTrue(role_includes(OrganizationRole.MEMBER, OrganizationRole.MEMBER))

    def test_a_role_does_not_include_the_ones_above(self):
        self.assertFalse(role_includes(OrganizationRole.MEMBER, OrganizationRole.ADMIN))
        self.assertFalse(role_includes(OrganizationRole.ADMIN, OrganizationRole.OWNER))

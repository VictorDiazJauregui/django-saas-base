from unittest import mock

from django.db import IntegrityError
from django.test import TestCase

from organizations.models import Membership, Organization
from organizations.organization_creation import create_organization_for
from organizations.slugs import build_unique_slug
from security.tests.user_factory import create_user

from .organization_factory import create_organization

SLUG_BUILDER = "organizations.models.build_unique_slug"


# Two requests that read the free slugs at the same time both pick "acme"; the test plays the
# second one by handing it the slug the first one already saved.
class SlugCollisionTests(TestCase):
    def setUp(self):
        self.owner = create_user()
        create_organization("Acme")

    def test_a_taken_slug_is_replaced_by_the_next_free_one(self):
        with mock.patch(SLUG_BUILDER, side_effect=["acme", build_unique_slug("Acme")]):
            organization = create_organization_for(self.owner, {"name": "Acme"})
        self.assertEqual(organization.slug, "acme-2")
        self.assertEqual(organization.memberships.get().user, self.owner)

    def test_nothing_is_left_behind_by_the_failed_attempt(self):
        with mock.patch(SLUG_BUILDER, side_effect=["acme", "acme-2"]):
            create_organization_for(self.owner, {"name": "Acme"})
        self.assertEqual(Organization.objects.count(), 2)
        self.assertEqual(Membership.objects.count(), 1)

    def test_it_gives_up_after_three_attempts(self):
        with (
            mock.patch(SLUG_BUILDER, return_value="acme"),
            self.assertRaises(IntegrityError),
        ):
            create_organization_for(self.owner, {"name": "Acme"})
        self.assertEqual(Organization.objects.count(), 1)

    def test_a_slug_chosen_by_the_user_is_not_changed(self):
        with self.assertRaises(IntegrityError):
            create_organization_for(self.owner, {"name": "Other", "slug": "acme"})

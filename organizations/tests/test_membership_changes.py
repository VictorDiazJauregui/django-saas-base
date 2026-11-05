import threading

from django.db import connection
from django.test import TestCase, TransactionTestCase

from organizations.membership_changes import (
    LastOwnerError,
    change_member_role,
    remove_member,
)
from organizations.models import Membership
from organizations.roles import OrganizationRole

from .organization_factory import create_member, create_organization


class ChangeMemberRoleTests(TestCase):
    def setUp(self):
        self.organization = create_organization()
        self.owner = create_member(self.organization, "owner@example.com", "owner")

    def test_changes_the_role(self):
        member = create_member(self.organization, "member@example.com")
        change_member_role(member, OrganizationRole.ADMIN)
        member.refresh_from_db()
        self.assertEqual(member.role, OrganizationRole.ADMIN)

    def test_promoting_to_owner_needs_no_other_owner(self):
        member = create_member(self.organization, "member@example.com")
        self.owner.delete()
        change_member_role(member, OrganizationRole.OWNER)
        member.refresh_from_db()
        self.assertEqual(member.role, OrganizationRole.OWNER)

    def test_the_last_owner_cannot_step_down(self):
        with self.assertRaises(LastOwnerError):
            change_member_role(self.owner, OrganizationRole.ADMIN)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.role, OrganizationRole.OWNER)

    def test_an_owner_steps_down_when_another_owner_remains(self):
        create_member(self.organization, "second@example.com", "owner")
        change_member_role(self.owner, OrganizationRole.MEMBER)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.role, OrganizationRole.MEMBER)

    def test_owners_of_other_organizations_do_not_count(self):
        other = create_organization("Globex")
        create_member(other, "other-owner@example.com", "owner")
        with self.assertRaises(LastOwnerError):
            change_member_role(self.owner, OrganizationRole.ADMIN)


class RemoveMemberTests(TestCase):
    def setUp(self):
        self.organization = create_organization()
        self.owner = create_member(self.organization, "owner@example.com", "owner")

    def test_removes_a_member(self):
        member = create_member(self.organization, "member@example.com")
        remove_member(member)
        self.assertFalse(Membership.objects.filter(pk=member.pk).exists())

    def test_the_last_owner_cannot_be_removed(self):
        with self.assertRaises(LastOwnerError):
            remove_member(self.owner)
        self.assertTrue(Membership.objects.filter(pk=self.owner.pk).exists())

    def test_an_owner_is_removed_when_another_owner_remains(self):
        create_member(self.organization, "second@example.com", "owner")
        remove_member(self.owner)
        self.assertFalse(Membership.objects.filter(pk=self.owner.pk).exists())


class ConcurrentOwnerRemovalTests(TransactionTestCase):
    def setUp(self):
        organization = create_organization()
        self.owners = [
            create_member(organization, "first@example.com", "owner"),
            create_member(organization, "second@example.com", "owner"),
        ]

    def remove_in_thread(self, membership, barrier, outcomes):
        barrier.wait()
        try:
            remove_member(membership)
            outcomes.append("removed")
        except LastOwnerError:
            outcomes.append("refused")
        finally:
            connection.close()

    def test_two_owners_removing_each_other_leave_one(self):
        barrier, outcomes = threading.Barrier(2), []
        threads = [
            threading.Thread(
                target=self.remove_in_thread, args=(owner, barrier, outcomes)
            )
            for owner in self.owners
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(outcomes), ["refused", "removed"])
        self.assertEqual(Membership.objects.filter(role="owner").count(), 1)

import threading

from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from core.tests.settings_subprocess import read_settings, run_manage_command
from organizations.api_errors import InvalidInvitation
from organizations.invitations import accept_invitation
from organizations.models import Invitation, Membership
from security.tests.user_factory import create_superuser, create_user
from webhooks.models import WebhookDelivery, WebhookEndpoint

from .invitation_helpers import INVITATION_URL, invite, with_invitations
from .organization_factory import create_organization


@with_invitations
class ConcurrentAcceptanceTests(TransactionTestCase):
    def setUp(self):
        _, self.token = invite(create_organization(), "new@example.com")
        self.user = create_user("new@example.com")

    def accept_in_thread(self, barrier, outcomes):
        barrier.wait()
        try:
            accept_invitation(self.user, self.token)
            outcomes.append("joined")
        except InvalidInvitation:
            outcomes.append("refused")
        finally:
            connection.close()

    def test_two_acceptances_of_one_token_create_one_membership(self):
        barrier, outcomes = threading.Barrier(2), []
        threads = [
            threading.Thread(target=self.accept_in_thread, args=(barrier, outcomes))
            for _ in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(outcomes), ["joined", "refused"])
        self.assertEqual(Membership.objects.count(), 1)


@with_invitations
@override_settings(WEBHOOKS_ENABLED=True)
class MemberAddedEventTests(TestCase):
    def test_accepting_emits_member_added(self):
        WebhookEndpoint.objects.create(
            url="https://hooks.example.com/in",
            events=["organization.member_added"],
            secret="test-secret",
        )
        organization = create_organization()
        _, token = invite(organization, "new@example.com", "admin")
        user = create_user("new@example.com")
        accept_invitation(user, token)
        delivery = WebhookDelivery.objects.get()
        self.assertEqual(delivery.event, "organization.member_added")
        expected = {
            "organization_id": str(organization.pk),
            "user_id": str(user.pk),
            "email": "new@example.com",
            "role": "admin",
        }
        self.assertEqual(delivery.payload, expected)


class InvitationModelTests(TestCase):
    def test_the_status_follows_the_dates(self):
        invitation, _ = invite(create_organization(), "new@example.com")
        self.assertEqual(invitation.status, Invitation.PENDING)
        invitation.revoked_at = invitation.created_at
        self.assertEqual(invitation.status, Invitation.REVOKED)
        invitation.accepted_at = invitation.created_at
        self.assertEqual(invitation.status, Invitation.ACCEPTED)

    def test_the_text_shows_email_and_organization(self):
        invitation, _ = invite(create_organization("Acme"), "new@example.com")
        self.assertEqual(str(invitation), "new@example.com → Acme")


@with_invitations
class InvitationAdminTests(TestCase):
    def setUp(self):
        self.client.force_login(create_superuser())
        self.invitation, self.token = invite(
            create_organization("Acme"), "new@example.com"
        )

    def test_the_list_shows_the_status_and_never_the_token(self):
        response = self.client.get(reverse("admin:organizations_invitation_changelist"))
        self.assertContains(response, "new@example.com")
        self.assertContains(response, "Pending")
        self.assertNotContains(response, self.token)
        self.assertNotContains(response, self.invitation.token_hash)

    def test_the_admin_revokes_invitations(self):
        url = reverse("admin:organizations_invitation_changelist")
        form = {
            "action": "revoke_invitations",
            "_selected_action": [self.invitation.pk],
        }
        self.client.post(url, form)
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, Invitation.REVOKED)

    def test_invitations_are_not_added_from_the_admin(self):
        response = self.client.get(reverse("admin:organizations_invitation_add"))
        self.assertEqual(response.status_code, 403)

    def test_a_staff_user_without_permission_cannot_revoke(self):
        staff = create_user("staff@example.com")
        staff.is_staff = True
        staff.save()
        staff.user_permissions.add(Permission.objects.get(codename="view_invitation"))
        self.client.force_login(staff)
        url = reverse("admin:organizations_invitation_changelist")
        self.client.post(
            url,
            {"action": "revoke_invitations", "_selected_action": [self.invitation.pk]},
        )
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, Invitation.PENDING)


class InvitationSettingsTests(TestCase):
    def test_turning_tenancy_on_needs_the_invitation_url(self):
        result = run_manage_command(["check"], TENANCY_ENABLED="True")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FRONTEND_INVITATION_URL", result.stderr)

    def test_the_invitation_url_needs_the_token_marker(self):
        url = "https://app.example.com/join"
        result = run_manage_command(
            ["check"], TENANCY_ENABLED="True", FRONTEND_INVITATION_URL=url
        )
        self.assertIn("{token}", result.stderr)

    def test_the_settings_come_from_the_environment(self):
        names = ["FRONTEND_INVITATION_URL", "TENANCY_INVITATION_TIMEOUT"]
        values = read_settings(
            names,
            TENANCY_ENABLED="True",
            FRONTEND_INVITATION_URL=INVITATION_URL,
            TENANCY_INVITATION_TIMEOUT_HOURS="24",
        )
        self.assertEqual(values["FRONTEND_INVITATION_URL"], INVITATION_URL)
        self.assertEqual(values["TENANCY_INVITATION_TIMEOUT"], 24 * 3600)

    def test_the_url_is_optional_with_tenancy_off(self):
        values = read_settings(["FRONTEND_INVITATION_URL"])
        self.assertEqual(values["FRONTEND_INVITATION_URL"], "")

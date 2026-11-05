from datetime import timedelta

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from organizations.invitations import hash_invitation_token
from organizations.models import Invitation, Membership
from security.models import AuditLog
from security.tests.api_test_case import LanguageResetAPITestCase
from security.tests.test_throttling import override_rates
from security.tests.user_factory import create_user

from .invitation_helpers import (
    invite,
    token_from_email,
    with_invitations,
    without_invitation_limit,
)
from .organization_factory import add_member, create_organization

NEW_PASSWORD = "Fresh-Passphrase-77"


@with_invitations
@without_invitation_limit
class InvitationApiTestCase(LanguageResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.organization = create_organization("Acme")
        self.admin = create_user("admin@example.com")
        self.admin_membership = add_member(self.organization, self.admin, "admin")

    def invitations_url(self):
        kwargs = {"organization_id": self.organization.pk}
        return reverse("organizations:invitations", kwargs=kwargs)

    def invitation_url(self, invitation):
        kwargs = {
            "organization_id": self.organization.pk,
            "invitation_id": invitation.pk,
        }
        return reverse("organizations:invitation", kwargs=kwargs)

    def post_as(self, user, url, payload):
        self.client.force_authenticate(user)
        return self.client.post(url, payload, format="json")

    def public_post(self, name, payload):
        self.client.force_authenticate(None)
        return self.client.post(reverse(f"invitations:{name}"), payload, format="json")

    def assert_error(self, response, status_code, code):
        self.assertEqual(response.status_code, status_code, response.content)
        self.assertEqual(response.json()["code"], code)


class InviteTests(InvitationApiTestCase):
    def invite_as_admin(self, email="new@example.com", role="member"):
        payload = {"email": email, "role": role}
        return self.post_as(self.admin, self.invitations_url(), payload)

    def test_an_admin_invites_and_the_email_carries_the_link(self):
        response = self.invite_as_admin("New@Example.com")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["email"], "new@example.com")
        self.assertEqual(response.json()["invited_by_email"], "admin@example.com")
        message = mail.outbox[0]
        self.assertEqual(message.to, ["new@example.com"])
        self.assertIn("Acme", message.subject)
        self.assertIn("https://app.example.com/join?token=", message.body)

    def test_only_the_hash_of_the_token_is_stored(self):
        self.invite_as_admin()
        token = token_from_email(mail.outbox[0])
        invitation = Invitation.objects.get()
        self.assertEqual(invitation.token_hash, hash_invitation_token(token))
        self.assertNotIn(token, str(Invitation.objects.values().get()))

    def test_the_answer_never_shows_the_token(self):
        body = self.invite_as_admin().json()
        self.assertEqual(
            set(body),
            {"id", "email", "role", "invited_by_email", "expires_at", "created_at"},
        )

    def test_inviting_again_replaces_the_pending_invitation(self):
        self.invite_as_admin()
        first_token = token_from_email(mail.outbox[0])
        self.invite_as_admin()
        self.assertEqual(Invitation.objects.filter(revoked_at__isnull=True).count(), 1)
        response = self.public_post("lookup", {"token": first_token})
        self.assert_error(response, status.HTTP_400_BAD_REQUEST, "invalid_invitation")

    def test_an_existing_member_cannot_be_invited(self):
        add_member(self.organization, create_user("member@example.com"))
        response = self.invite_as_admin("MEMBER@example.com")
        self.assert_error(response, status.HTTP_409_CONFLICT, "already_member")
        self.assertEqual(len(mail.outbox), 0)

    def test_an_admin_cannot_invite_an_owner(self):
        response = self.invite_as_admin(role="owner")
        self.assert_error(response, status.HTTP_403_FORBIDDEN, "permission_denied")
        self.assertFalse(Invitation.objects.exists())

    def test_an_owner_invites_an_owner(self):
        owner = create_user("owner@example.com")
        add_member(self.organization, owner, "owner")
        payload = {"email": "co-owner@example.com", "role": "owner"}
        response = self.post_as(owner, self.invitations_url(), payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_a_member_cannot_invite(self):
        member = create_user("member@example.com")
        add_member(self.organization, member)
        payload = {"email": "new@example.com", "role": "member"}
        response = self.post_as(member, self.invitations_url(), payload)
        self.assert_error(response, status.HTTP_403_FORBIDDEN, "permission_denied")

    def test_the_email_and_role_are_validated(self):
        response = self.invite_as_admin(email="not-an-email", role="boss")
        self.assertEqual(set(response.json()["fields"]), {"email", "role"})

    def test_an_admin_lists_and_revokes_the_pending_invitations(self):
        invitation, _ = invite(self.organization, "new@example.com")
        self.client.force_authenticate(self.admin)
        listed = self.client.get(self.invitations_url()).json()["results"]
        self.assertEqual([item["email"] for item in listed], ["new@example.com"])
        response = self.client.delete(self.invitation_url(invitation))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.client.get(self.invitations_url()).json()["count"], 0)

    def test_a_member_cannot_list_invitations(self):
        member = create_user("member@example.com")
        add_member(self.organization, member)
        self.client.force_authenticate(member)
        response = self.client.get(self.invitations_url())
        self.assert_error(response, status.HTTP_403_FORBIDDEN, "permission_denied")

    @override_settings(TENANCY_ENABLED=False)
    def test_with_the_module_off_the_routes_do_not_exist(self):
        response = self.public_post("lookup", {"token": "anything"})
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "not_found")
        response = self.invite_as_admin()
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "not_found")


class LookupTests(InvitationApiTestCase):
    def test_describes_the_invitation_for_the_frontend(self):
        invitation, token = invite(self.organization, "new@example.com", "admin")
        body = self.public_post("lookup", {"token": token}).json()
        self.assertEqual(body["organization"]["name"], "Acme")
        self.assertEqual(body["email"], "new@example.com")
        self.assertEqual(body["role"], "admin")
        self.assertFalse(body["account_exists"])

    def test_tells_whether_the_email_already_has_an_account(self):
        create_user("new@example.com")
        _, token = invite(self.organization, "new@example.com")
        self.assertTrue(
            self.public_post("lookup", {"token": token}).json()["account_exists"]
        )

    def test_unknown_expired_and_revoked_tokens_get_the_same_answer(self):
        expired, expired_token = invite(self.organization, "old@example.com")
        Invitation.objects.filter(pk=expired.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        revoked, revoked_token = invite(self.organization, "gone@example.com")
        Invitation.objects.filter(pk=revoked.pk).update(revoked_at=timezone.now())
        for token in ("not-a-token", expired_token, revoked_token):
            with self.subTest(token=token[:8]):
                response = self.public_post("lookup", {"token": token})
                self.assert_error(response, 400, "invalid_invitation")


class AcceptTests(InvitationApiTestCase):
    def setUp(self):
        super().setUp()
        self.invitation, self.token = invite(
            self.organization, "new@example.com", "admin"
        )
        self.invitee = create_user("NEW@example.com")

    def accept(self, user, token=None):
        url = reverse("invitations:accept")
        return self.post_as(user, url, {"token": token or self.token})

    def test_the_invited_user_joins_with_the_role(self):
        response = self.accept(self.invitee)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["role"], "admin")
        self.assertEqual(response.json()["id"], str(self.organization.pk))
        membership = Membership.objects.get(user=self.invitee)
        self.assertEqual(membership.role, "admin")
        self.invitation.refresh_from_db()
        self.assertIsNotNone(self.invitation.accepted_at)

    def test_the_token_works_once(self):
        self.accept(self.invitee)
        response = self.accept(self.invitee)
        self.assert_error(response, status.HTTP_400_BAD_REQUEST, "invalid_invitation")

    def test_another_account_cannot_use_it(self):
        response = self.accept(create_user("other@example.com"))
        self.assert_error(
            response, status.HTTP_403_FORBIDDEN, "invitation_email_mismatch"
        )
        self.assertFalse(
            Membership.objects.filter(user__email="other@example.com").exists()
        )

    def test_without_a_token_asks_for_credentials(self):
        self.client.force_authenticate(None)
        response = self.client.post(
            reverse("invitations:accept"), {"token": self.token}
        )
        self.assert_error(response, status.HTTP_401_UNAUTHORIZED, "not_authenticated")

    def test_a_user_already_in_the_organization_gets_a_conflict(self):
        add_member(self.organization, self.invitee)
        response = self.accept(self.invitee)
        self.assert_error(response, status.HTTP_409_CONFLICT, "already_member")


class RegisterFromInvitationTests(InvitationApiTestCase):
    def setUp(self):
        super().setUp()
        self.invitation, self.token = invite(self.organization, "new@example.com")

    def register(self, **overrides):
        payload = {
            "token": self.token,
            "password": NEW_PASSWORD,
            "password2": NEW_PASSWORD,
            "first_name": "Nora",
            "last_name": "New",
            **overrides,
        }
        return self.public_post("register", payload)

    @override_settings(ALLOW_PUBLIC_REGISTRATION=False, REQUIRE_EMAIL_VERIFICATION=True)
    def test_creates_a_verified_account_even_with_registration_closed(self):
        response = self.register()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["role"], "member")
        membership = Membership.objects.select_related("user").get(
            user__email="new@example.com"
        )
        self.assertTrue(membership.user.is_email_verified)
        self.assertTrue(membership.user.check_password(NEW_PASSWORD))
        login = self.client.post(
            reverse("security:login"),
            {"email": "new@example.com", "password": NEW_PASSWORD},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_an_email_with_an_account_must_log_in_instead(self):
        create_user("new@example.com")
        response = self.register()
        self.assert_error(response, status.HTTP_409_CONFLICT, "account_exists")
        self.assertEqual(
            response.json()["detail"],
            "An account with this email already exists. Log in with its password.",
        )

    def test_the_password_policy_applies(self):
        response = self.register(password="short", password2="short")
        self.assertIn("password", response.json()["fields"])
        self.assertFalse(
            Membership.objects.filter(user__email="new@example.com").exists()
        )

    def test_the_passwords_must_match(self):
        response = self.register(password2="Other-Passphrase-77")
        self.assertIn("password", response.json()["fields"])

    def test_the_token_works_once(self):
        self.register()
        response = self.register(first_name="Again")
        self.assert_error(response, status.HTTP_400_BAD_REQUEST, "invalid_invitation")

    def test_the_audit_log_keeps_neither_token_nor_password(self):
        self.register()
        payload = AuditLog.objects.get(path=reverse("invitations:register")).payload
        self.assertEqual(payload["token"], "[REDACTED]")
        self.assertEqual(payload["password"], "[REDACTED]")
        self.assertEqual(payload["password2"], "[REDACTED]")


class InvitationThrottleTests(InvitationApiTestCase):
    def test_the_public_routes_are_rate_limited(self):
        with override_rates(invitation="2/h"):
            for _ in range(2):
                self.public_post("lookup", {"token": "x"})
            response = self.public_post("lookup", {"token": "x"})
        self.assert_error(response, status.HTTP_429_TOO_MANY_REQUESTS, "throttled")


class InvitationLanguageTests(InvitationApiTestCase):
    def test_the_email_follows_the_language_of_the_request(self):
        self.client.force_authenticate(self.admin)
        payload = {"email": "nuevo@example.com", "role": "member"}
        self.client.post(
            self.invitations_url(), payload, format="json", HTTP_ACCEPT_LANGUAGE="es"
        )
        self.assertIn("Te invitaron", mail.outbox[0].subject)

    def test_the_invalid_token_message_is_translated(self):
        self.client.force_authenticate(None)
        response = self.client.post(
            reverse("invitations:lookup"),
            {"token": "x"},
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertIn("invitación", response.json()["detail"])

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from organizations.api_key_actor import OrganizationApiKeyActor
from organizations.models import OrganizationApiKey
from security.api_keys import issue_api_key
from security.models import AuditLog
from security.tests.api_test_case import CacheResetAPITestCase
from security.tests.user_factory import create_user

from .organization_factory import (
    add_member,
    create_organization,
    create_organization_api_key,
)
from .scoped_project import Project, create_project_table
from .test_permissions import TEST_URLS

INVALID_API_KEY_BODY = {
    "code": "invalid_api_key",
    "detail": "Invalid API key.",
    "fields": {},
}


@override_settings(TENANCY_ENABLED=True, API_KEYS_ENABLED=True)
class OrganizationApiKeyTestCase(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.acme, self.globex = create_organization("Acme"), create_organization(
            "Globex"
        )
        self.api_key, self.raw_key = create_organization_api_key(self.acme)

    def use_key(self, raw_key: str) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}")

    def assert_error(self, response, status_code: int, code: str) -> None:
        self.assertEqual(response.status_code, status_code, response.content)
        self.assertEqual(response.json()["code"], code)


class OrganizationApiKeyRecordTests(OrganizationApiKeyTestCase):
    def test_stores_only_the_hash_and_a_typed_prefix(self):
        self.assertTrue(self.raw_key.startswith(f"{self.api_key.prefix}."))
        self.assertTrue(self.api_key.prefix.startswith("org_"))
        self.assertNotIn(self.raw_key, self.api_key.key_hash)
        stored = OrganizationApiKey.objects.values().get(pk=self.api_key.pk)
        self.assertNotIn(self.raw_key, [str(value) for value in stored.values()])

    def test_the_actor_reads_as_its_key(self):
        actor = OrganizationApiKeyActor(self.api_key)
        self.assertEqual(str(actor), f"ERP ({self.api_key.prefix})")
        self.assertFalse(actor.is_authenticated)

    def test_the_owner_role_is_refused_by_the_database(self):
        self.api_key.role = "owner"
        with self.assertRaises(IntegrityError) as raised, transaction.atomic():
            self.api_key.save()
        self.assertIn("organization_api_key_role", str(raised.exception))


@override_settings(ROOT_URLCONF=TEST_URLS)
class OrganizationApiKeyScopedRouteTests(OrganizationApiKeyTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_project_table()

    def setUp(self):
        super().setUp()
        Project.objects.create(organization=self.acme, name="Rocket")
        Project.objects.create(organization=self.globex, name="Secret")
        self.use_key(self.raw_key)

    def projects_url(self, organization_reference: object) -> str:
        return reverse(
            "project-list", kwargs={"organization_id": organization_reference}
        )

    def test_the_key_lists_only_the_rows_of_its_organization(self):
        response = self.client.get(self.projects_url(self.acme.pk))
        names = [row["name"] for row in response.json()["results"]]
        self.assertEqual(names, ["Rocket"])

    def test_the_key_creates_rows_in_its_organization(self):
        response = self.client.post(self.projects_url("acme"), {"name": "Probe"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Project.objects.get(name="Probe").organization, self.acme)

    def test_the_key_of_acme_on_globex_is_not_found_by_id_and_by_slug(self):
        for reference in (self.globex.pk, "globex"):
            with self.subTest(reference=reference):
                response = self.client.get(self.projects_url(reference))
                self.assert_error(response, 404, "organization_not_found")

    def test_a_member_key_is_denied_an_admin_route(self):
        url = reverse("admin_only", kwargs={"organization_id": "acme"})
        self.assert_error(self.client.get(url), 403, "permission_denied")

    def test_an_admin_key_passes_an_admin_route(self):
        _, raw_key = create_organization_api_key(self.acme, "admin", name="Admin")
        self.use_key(raw_key)
        url = reverse("echo", kwargs={"organization_id": "acme"})
        response = self.client.get(url)
        self.assertEqual(response.json(), {"slug": "acme", "role": "admin"})

    def test_the_key_keeps_working_when_its_creator_leaves(self):
        creator = create_user()
        membership = add_member(self.acme, creator, "admin")
        _, raw_key = create_organization_api_key(self.acme, created_by=creator)
        membership.delete()
        creator.delete()
        self.use_key(raw_key)
        response = self.client.get(self.projects_url("acme"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_an_action_with_the_key_is_audited_with_its_prefix_and_organization(self):
        self.client.post(self.projects_url("acme"), {"name": "Probe"})
        entry = AuditLog.objects.get()
        self.assertIsNone(entry.user)
        self.assertEqual(entry.api_key_prefix, self.api_key.prefix)
        self.assertEqual(entry.organization_id, self.acme.pk)
        self.assertNotIn(self.raw_key, str(entry.payload))


@override_settings(ROOT_URLCONF=TEST_URLS)
class OrganizationApiKeyRejectionTests(OrganizationApiKeyTestCase):
    url = "/api/v1/organizations/acme/echo/"

    def assert_rejected(self, raw_key: str) -> None:
        self.use_key("0123456789ab.not-a-personal-key")
        with self.settings(API_KEYS_ENABLED=True, TENANCY_ENABLED=True):
            personal = self.client.get(self.url)
        self.use_key(raw_key)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json(), INVALID_API_KEY_BODY)
        self.assertEqual(response.json(), personal.json())
        self.assertEqual(response["WWW-Authenticate"], personal["WWW-Authenticate"])

    def test_a_revoked_key_gets_the_personal_key_answer(self):
        OrganizationApiKey.objects.update(revoked_at=timezone.now())
        self.assert_rejected(self.raw_key)

    def test_an_expired_key_gets_the_same_answer(self):
        OrganizationApiKey.objects.update(expires_at=timezone.now())
        self.assert_rejected(self.raw_key)

    def test_a_wrong_secret_gets_the_same_answer(self):
        self.assert_rejected(f"{self.api_key.prefix}.wrong-secret")

    def test_an_unknown_typed_key_gets_the_same_answer(self):
        self.assert_rejected("org_000000000000.garbage")

    @override_settings(TENANCY_ENABLED=False)
    def test_with_tenancy_off_the_key_gets_the_same_answer(self):
        self.assert_rejected(self.raw_key)

    @override_settings(API_KEYS_ENABLED=False)
    def test_with_api_keys_off_the_key_gets_the_same_answer(self):
        self.assert_rejected(self.raw_key)


@override_settings(ROOT_URLCONF=TEST_URLS)
class OrganizationApiKeyLastUseTests(OrganizationApiKeyTestCase):
    url = "/api/v1/organizations/acme/echo/"

    def last_used_at(self):
        self.api_key.refresh_from_db()
        return self.api_key.last_used_at

    def test_the_first_use_is_recorded(self):
        self.use_key(self.raw_key)
        self.client.get(self.url)
        self.assertIsNotNone(self.last_used_at())

    def test_a_recent_use_is_not_written_again(self):
        recent = timezone.now() - timedelta(minutes=1)
        OrganizationApiKey.objects.update(last_used_at=recent)
        self.use_key(self.raw_key)
        self.client.get(self.url)
        self.assertEqual(self.last_used_at(), recent)

    def test_an_old_use_is_refreshed(self):
        old = timezone.now() - timedelta(minutes=10)
        OrganizationApiKey.objects.update(last_used_at=old)
        self.use_key(self.raw_key)
        self.client.get(self.url)
        self.assertGreater(self.last_used_at(), old)


class OrganizationApiKeyPersonRouteTests(OrganizationApiKeyTestCase):
    def setUp(self):
        super().setUp()
        self.use_key(self.raw_key)

    def test_a_route_that_needs_a_person_is_forbidden(self):
        response = self.client.get(reverse("security:me"))
        self.assert_error(response, 403, "permission_denied")

    def test_the_management_routes_of_the_module_are_forbidden(self):
        urls = [reverse("organizations:list")] + [
            reverse(f"organizations:{name}", kwargs={"organization_id": "acme"})
            for name in ("detail", "members", "invitations", "api_keys")
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assert_error(response, 403, "organization_api_key_not_allowed")

    def test_the_personal_key_keeps_working(self):
        _, personal_key = issue_api_key(create_user(), "Billing")
        self.use_key(personal_key)
        self.assertEqual(
            self.client.get(reverse("security:me")).status_code, status.HTTP_200_OK
        )

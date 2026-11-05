import uuid
from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from organizations.models import OrganizationApiKey
from security.models import AuditLog
from security.redaction import is_sensitive_key
from security.tests.api_test_case import CacheResetAPITestCase
from security.tests.user_factory import create_user

from .organization_factory import (
    add_member,
    create_organization,
    create_organization_api_key,
)

LISTED_FIELDS = {
    "id",
    "name",
    "prefix",
    "role",
    "created_by_email",
    "expires_at",
    "last_used_at",
    "revoked_at",
    "created_at",
}


def api_keys_url(organization_reference: object) -> str:
    return reverse(
        "organizations:api_keys", kwargs={"organization_id": organization_reference}
    )


def api_key_url(organization_reference: object, key_id: object) -> str:
    kwargs = {"organization_id": organization_reference, "key_id": key_id}
    return reverse("organizations:api_key", kwargs=kwargs)


@override_settings(TENANCY_ENABLED=True, API_KEYS_ENABLED=True)
class OrganizationApiKeyApiTestCase(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.organization = create_organization("Acme")
        self.user = create_user()

    def join(self, role: str) -> None:
        add_member(self.organization, self.user, role)
        self.client.force_authenticate(self.user)

    def create_key(self, payload: dict, organization_reference: object = "acme"):
        return self.client.post(
            api_keys_url(organization_reference), payload, format="json"
        )

    def assert_error(self, response, status_code: int, code: str) -> None:
        self.assertEqual(response.status_code, status_code, response.content)
        self.assertEqual(response.json()["code"], code)


class OrganizationApiKeyCreateTests(OrganizationApiKeyApiTestCase):
    def test_an_admin_gets_the_key_once_with_its_record(self):
        self.join("admin")
        response = self.create_key({"name": "ERP", "role": "member"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertEqual(set(body), LISTED_FIELDS | {"api_key"})
        self.assertTrue(body["api_key"].startswith(f"{body['prefix']}."))
        self.assertEqual(body["created_by_email"], self.user.email)

    def test_an_owner_creates_an_admin_key_by_id(self):
        self.join("owner")
        payload = {"name": "Sync", "role": "admin"}
        response = self.create_key(payload, self.organization.pk)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OrganizationApiKey.objects.get().role, "admin")

    def test_a_member_cannot_create_a_key(self):
        self.join("member")
        response = self.create_key({"name": "ERP", "role": "member"})
        self.assert_error(response, status.HTTP_403_FORBIDDEN, "permission_denied")
        self.assertFalse(OrganizationApiKey.objects.exists())

    def test_the_owner_role_is_a_field_error(self):
        self.join("owner")
        response = self.create_key({"name": "ERP", "role": "owner"})
        self.assert_error(response, status.HTTP_400_BAD_REQUEST, "invalid")
        self.assertIn("role", response.json()["fields"])

    def test_a_past_expiry_is_a_field_error(self):
        self.join("admin")
        past = (timezone.now() - timedelta(minutes=1)).isoformat()
        response = self.create_key(
            {"name": "ERP", "role": "member", "expires_at": past}
        )
        self.assertIn("expires_at", response.json()["fields"])

    def test_a_future_expiry_is_kept(self):
        self.join("admin")
        future = timezone.now() + timedelta(days=30)
        payload = {"name": "ERP", "role": "member", "expires_at": future.isoformat()}
        self.create_key(payload)
        self.assertEqual(OrganizationApiKey.objects.get().expires_at, future)

    def test_the_name_is_required(self):
        self.join("admin")
        response = self.create_key({"role": "member"})
        self.assertIn("name", response.json()["fields"])

    def test_the_key_is_kept_out_of_the_audit_log(self):
        self.join("admin")
        raw_key = self.create_key({"name": "ERP", "role": "member"}).json()["api_key"]
        self.assertNotIn(raw_key, str(AuditLog.objects.get().payload))
        self.assertTrue(is_sensitive_key("api_key"))

    def test_without_a_token_asks_for_credentials(self):
        response = self.create_key({"name": "ERP", "role": "member"})
        self.assert_error(response, status.HTTP_401_UNAUTHORIZED, "not_authenticated")


class OrganizationApiKeyListTests(OrganizationApiKeyApiTestCase):
    def test_lists_the_keys_of_the_organization_without_secrets(self):
        self.join("admin")
        create_organization_api_key(self.organization)
        create_organization_api_key(create_organization("Globex"))
        results = self.client.get(api_keys_url("acme")).json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(set(results[0]), LISTED_FIELDS)

    def test_a_member_cannot_list_the_keys(self):
        self.join("member")
        self.assert_error(
            self.client.get(api_keys_url("acme")), 403, "permission_denied"
        )

    @override_settings(TENANCY_ENABLED=False)
    def test_with_tenancy_off_the_route_does_not_exist(self):
        self.join("admin")
        self.assert_error(self.client.get(api_keys_url("acme")), 404, "not_found")

    @override_settings(API_KEYS_ENABLED=False)
    def test_with_api_keys_off_the_route_does_not_exist(self):
        self.join("admin")
        self.assert_error(self.client.get(api_keys_url("acme")), 404, "not_found")


class OrganizationApiKeyRevokeTests(OrganizationApiKeyApiTestCase):
    def setUp(self):
        super().setUp()
        self.join("admin")
        self.api_key, _ = create_organization_api_key(self.organization)

    def test_revoking_keeps_the_row_and_marks_it(self):
        response = self.client.delete(api_key_url("acme", self.api_key.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.api_key.refresh_from_db()
        self.assertIsNotNone(self.api_key.revoked_at)

    def test_revoking_twice_keeps_the_first_date(self):
        self.client.delete(api_key_url("acme", self.api_key.pk))
        first = OrganizationApiKey.objects.get().revoked_at
        response = self.client.delete(api_key_url("acme", self.api_key.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(OrganizationApiKey.objects.get().revoked_at, first)

    def test_a_key_of_another_organization_is_not_found(self):
        globex = create_organization("Globex")
        add_member(globex, self.user, "admin")
        response = self.client.delete(api_key_url("globex", self.api_key.pk))
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "not_found")
        self.assertIsNone(OrganizationApiKey.objects.get().revoked_at)

    def test_an_unknown_key_is_not_found(self):
        response = self.client.delete(api_key_url("acme", uuid.uuid4()))
        self.assert_error(response, status.HTTP_404_NOT_FOUND, "not_found")

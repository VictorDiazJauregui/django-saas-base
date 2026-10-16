import uuid

from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken

from security.models import AuditLog

from .api_test_case import CacheResetAPITestCase
from .user_factory import create_user

PROFILE_URL = "/api/v1/auth/me/"
PROFILE_FIELDS = {"id", "email", "first_name", "last_name", "date_joined"}


class ProfileTestCase(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user()
        self.user.first_name, self.user.last_name = "Jane", "Doe"
        self.user.save()
        self.authenticate(self.user)

    def authenticate(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}"
        )

    def update_profile(self, payload):
        return self.client.patch(PROFILE_URL, payload, format="json")


class ProfileReadTests(ProfileTestCase):
    def test_returns_the_profile_of_the_authenticated_user(self):
        response = self.client.get(PROFILE_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), PROFILE_FIELDS)
        self.assertEqual(response.data["id"], str(self.user.pk))
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["first_name"], "Jane")

    def test_each_user_only_sees_their_own_profile(self):
        other = create_user(email="other@example.com")
        self.authenticate(other)

        response = self.client.get(PROFILE_URL)

        self.assertEqual(response.data["id"], str(other.pk))


class ProfileAuthenticationTests(ProfileTestCase):
    def test_anonymous_request_is_unauthorized(self):
        self.client.credentials()

        response = self.client.get(PROFILE_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token_is_unauthorized(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")

        response = self.client.get(PROFILE_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileUpdateTests(ProfileTestCase):
    def test_updates_first_and_last_name(self):
        response = self.update_profile({"first_name": "Ana", "last_name": "Pérez"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name), ("Ana", "Pérez"))
        self.assertEqual(response.data["last_name"], "Pérez")

    def test_read_only_fields_are_ignored(self):
        original_email, original_id = self.user.email, self.user.pk
        payload = {
            "email": "attacker@example.com",
            "is_staff": True,
            "id": str(uuid.uuid4()),
            "date_joined": "2000-01-01T00:00:00Z",
        }

        response = self.update_profile(payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, original_email)
        self.assertEqual(self.user.pk, original_id)
        self.assertFalse(self.user.is_staff)
        self.assertNotEqual(self.user.date_joined.year, 2000)

    def test_rejects_a_name_longer_than_150_characters(self):
        response = self.update_profile({"first_name": "x" * 151})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("first_name", response.data)

    def test_records_the_update_in_the_audit_log(self):
        self.update_profile({"first_name": "Ana"})

        audit = AuditLog.objects.filter(path=PROFILE_URL).latest("timestamp")
        self.assertEqual(audit.user, self.user)
        self.assertEqual(audit.status_code, status.HTTP_200_OK)


class ProfileMethodTests(ProfileTestCase):
    def test_only_get_and_patch_are_allowed(self):
        for method in ("put", "post", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    PROFILE_URL, {"first_name": "Ana"}, format="json"
                )

                self.assertEqual(
                    response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
                )

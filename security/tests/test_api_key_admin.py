from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from security.api_keys import hash_api_key, issue_api_key
from security.models import ApiKey, AuditLog

from .user_factory import create_superuser, create_user

CHANGELIST_URL = "admin:security_apikey_changelist"
ADD_URL = "admin:security_apikey_add"


class ApiKeyAdminTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = create_superuser()
        cls.owner = create_user()

    def setUp(self):
        self.client.force_login(self.superuser)

    def add_key(self, name="billing server"):
        form_data = {"user": str(self.owner.pk), "name": name, "expires_at_0": ""}
        return self.client.post(reverse(ADD_URL), form_data)


class ApiKeyCreationTests(ApiKeyAdminTestCase):
    def test_the_add_form_asks_only_for_user_name_and_expiry(self):
        response = self.client.get(reverse(ADD_URL))

        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="expires_at_0"')
        self.assertNotContains(response, 'name="prefix"')
        self.assertNotContains(response, 'name="key_hash"')

    def test_creating_a_key_shows_it_once(self):
        response = self.add_key()

        api_key = ApiKey.objects.get()
        raw_key = response.context["raw_key"]
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, raw_key)
        self.assertEqual(api_key.key_hash, hash_api_key(raw_key))
        self.assertEqual(api_key.user, self.owner)
        self.assertIn("no-store", response["Cache-Control"])

    def test_the_key_is_not_shown_again(self):
        raw_key = self.add_key().context["raw_key"]
        api_key = ApiKey.objects.get()

        detail = self.client.get(
            reverse("admin:security_apikey_change", args=[api_key.pk])
        )
        listing = self.client.get(reverse(CHANGELIST_URL))

        self.assertNotContains(detail, raw_key)
        self.assertNotContains(listing, raw_key)
        self.assertNotContains(detail, api_key.key_hash)
        self.assertContains(listing, api_key.prefix)

    def test_the_audit_log_of_the_creation_has_no_key(self):
        raw_key = self.add_key().context["raw_key"]

        record = AuditLog.objects.get(path=reverse(ADD_URL))
        self.assertNotIn(raw_key, str(record.payload))
        self.assertNotIn(raw_key.partition(".")[2], str(record.payload))


class ApiKeyDetailTests(ApiKeyAdminTestCase):
    def test_a_key_can_not_be_edited(self):
        api_key = issue_api_key(self.owner, "billing server")[0]
        url = reverse("admin:security_apikey_change", args=[api_key.pk])

        self.client.post(url, {"name": "renamed"})

        api_key.refresh_from_db()
        self.assertEqual(api_key.name, "billing server")
        self.assertNotContains(self.client.get(url), 'name="_save"')


class ApiKeyRevocationTests(ApiKeyAdminTestCase):
    def revoke(self, *api_keys):
        return self.client.post(
            reverse(CHANGELIST_URL),
            {
                "action": "revoke_selected",
                "_selected_action": [str(api_key.pk) for api_key in api_keys],
            },
            follow=True,
        )

    def test_revokes_the_selected_keys(self):
        first = issue_api_key(self.owner, "a")[0]
        second = issue_api_key(self.owner, "b")[0]
        kept = issue_api_key(self.owner, "c")[0]

        response = self.revoke(first, second)

        self.assertContains(response, "2 API keys revoked.")
        self.assertEqual(ApiKey.objects.filter(revoked_at__isnull=False).count(), 2)
        kept.refresh_from_db()
        self.assertIsNone(kept.revoked_at)

    def test_an_already_revoked_key_is_not_counted(self):
        api_key = issue_api_key(self.owner, "a")[0]
        self.revoke(api_key)

        response = self.revoke(api_key)

        self.assertContains(response, "0 API keys revoked.")

    def test_staff_without_the_change_permission_can_not_revoke(self):
        viewer = create_user(email="viewer@example.com")
        viewer.is_staff = True
        viewer.save()
        viewer.user_permissions.add(Permission.objects.get(codename="view_apikey"))
        self.client.force_login(viewer)

        response = self.client.get(reverse(CHANGELIST_URL))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "revoke_selected")

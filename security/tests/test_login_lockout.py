from datetime import timedelta
from io import StringIO

from axes.models import AccessAttempt
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from .api_test_case import CacheResetAPITestCase
from .test_throttling import WRONG_PASSWORD, override_rates
from .user_factory import (
    DEFAULT_EMAIL,
    DEFAULT_PASSWORD,
    create_superuser,
    create_user,
)

User = get_user_model()

LOGIN_URL = reverse("security:login")
ADMIN_LOGIN_URL = reverse("admin:login")
ATTEMPTS_URL = reverse("admin:axes_accessattempt_changelist")
OTHER_CLIENT_IP = "198.51.100.7"
COOL_OFF_SECONDS = 15 * 60
FAILURE_LIMIT = 5


# The login throttle (10 per 10 minutes) is turned off so every response comes from the
# lockout; a fast hasher keeps the repeated logins cheap.
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
@override_rates(login=None)
class LockoutTestCase(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user()

    def log_in(self, password=DEFAULT_PASSWORD, email=DEFAULT_EMAIL, **headers):
        payload = {"email": email, "password": password}
        return self.client.post(LOGIN_URL, payload, format="json", **headers)

    def fail_logins(self, times, **headers):
        return [
            self.log_in(WRONG_PASSWORD, **headers).status_code for _ in range(times)
        ]


class ApiLockoutTests(LockoutTestCase):
    def test_the_fifth_failure_locks_the_account(self):
        statuses = self.fail_logins(FAILURE_LIMIT)

        self.assertEqual(statuses, [401] * 4 + [429])

    def test_the_right_password_is_refused_while_locked(self):
        self.fail_logins(FAILURE_LIMIT)

        response = self.log_in()

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response["Retry-After"], str(COOL_OFF_SECONDS))
        self.assertIn("Too many failed login attempts", response.data["detail"])
        self.assertIn(f"{COOL_OFF_SECONDS} seconds", response.data["detail"])

    def test_other_casing_of_the_email_is_still_locked(self):
        self.fail_logins(FAILURE_LIMIT)

        response = self.log_in(email=DEFAULT_EMAIL.upper())

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_the_same_account_from_another_ip_can_log_in(self):
        self.fail_logins(FAILURE_LIMIT)

        response = self.log_in(REMOTE_ADDR=OTHER_CLIENT_IP)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_behind_a_proxy_the_forwarded_ip_is_locked(self):
        locked_client = {"HTTP_X_FORWARDED_FOR": "203.0.113.10"}
        self.fail_logins(FAILURE_LIMIT, **locked_client)

        locked = self.log_in(**locked_client)
        other = self.log_in(HTTP_X_FORWARDED_FOR="203.0.113.11")

        self.assertEqual(locked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(other.status_code, status.HTTP_200_OK)

    def test_the_account_unlocks_after_the_cool_off(self):
        self.fail_logins(FAILURE_LIMIT)
        past = timezone.now() - timedelta(seconds=COOL_OFF_SECONDS + 60)
        AccessAttempt.objects.update(attempt_time=past)

        response = self.log_in()

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_successful_login_resets_the_failures(self):
        first_round = self.fail_logins(FAILURE_LIMIT - 1)
        success = self.log_in()
        second_round = self.fail_logins(FAILURE_LIMIT - 1)

        self.assertEqual(first_round + second_round, [401] * 8)
        self.assertEqual(success.status_code, status.HTTP_200_OK)
        self.assertEqual(self.log_in().status_code, status.HTTP_200_OK)

    def test_axes_reset_unlocks_the_account(self):
        self.fail_logins(FAILURE_LIMIT)

        call_command("axes_reset", stdout=StringIO())

        self.assertEqual(self.log_in().status_code, status.HTTP_200_OK)

    def test_a_successful_login_updates_last_login(self):
        self.assertIsNone(self.user.last_login)

        self.log_in()

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)


class LockoutRecordTests(LockoutTestCase):
    def test_the_attempt_is_stored_by_lowercase_email_without_the_password(self):
        self.fail_logins(2)
        self.log_in(WRONG_PASSWORD, email=DEFAULT_EMAIL.upper())

        attempt = AccessAttempt.objects.get()
        self.assertEqual(attempt.username, DEFAULT_EMAIL)
        self.assertEqual(attempt.failures_since_start, 3)
        self.assertNotIn(WRONG_PASSWORD, attempt.post_data)
        self.assertNotIn(WRONG_PASSWORD, attempt.get_data)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AdminLockoutTests(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.superuser = create_superuser()

    def admin_log_in(self, password):
        credentials = {"username": self.superuser.email, "password": password}
        return self.client.post(ADMIN_LOGIN_URL, credentials)

    def test_the_admin_login_shows_the_lockout_page(self):
        statuses = [self.admin_log_in(WRONG_PASSWORD).status_code for _ in range(4)]
        locked = self.admin_log_in(WRONG_PASSWORD)

        self.assertEqual(statuses, [200] * 4)
        self.assertEqual(locked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertContains(locked, "Too many failed login attempts", status_code=429)
        self.assertContains(locked, "15 minutes", status_code=429)

    def test_the_right_password_is_refused_while_locked(self):
        for _ in range(FAILURE_LIMIT):
            self.admin_log_in(WRONG_PASSWORD)

        response = self.admin_log_in(DEFAULT_PASSWORD)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_failures_count_for_the_account(self):
        self.admin_log_in(WRONG_PASSWORD)

        self.assertEqual(AccessAttempt.objects.get().username, self.superuser.email)


class AttemptsAdminPermissionTests(CacheResetAPITestCase):
    def test_a_superuser_sees_the_attempts(self):
        self.client.force_login(create_superuser())

        response = self.client.get(ATTEMPTS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_staff_without_permission_cannot_see_them(self):
        staff = create_user(email="staff@example.com")
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])
        self.client.force_login(staff)

        response = self.client.get(ATTEMPTS_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
@override_rates()
class ThrottleAndLockoutTests(CacheResetAPITestCase):
    def test_the_throttle_still_stops_failures_spread_over_accounts(self):
        statuses = [
            self.client.post(
                LOGIN_URL,
                {"email": f"user.{number}@example.com", "password": WRONG_PASSWORD},
                format="json",
            ).status_code
            for number in range(11)
        ]

        self.assertEqual(statuses, [401] * 10 + [429])

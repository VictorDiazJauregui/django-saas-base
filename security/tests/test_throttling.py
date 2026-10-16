import time
from unittest import mock

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from core.throttling import ScopedRateThrottle

from .api_test_case import CacheResetAPITestCase
from .user_factory import DEFAULT_EMAIL, DEFAULT_PASSWORD, create_user

LOGIN_URL = reverse("security:login")
REGISTER_URL = reverse("security:register")
REFRESH_URL = reverse("security:token_refresh")
WRONG_PASSWORD = "Wrong-Passphrase-1"
TEN_MINUTES = 600
DEFAULT_RATES = {
    "anon": None,
    "user": None,
    "login": "10/10m",
    "register": "5/h",
    "password": "5/h",
    "verify_email": "5/h",
}


def override_rates(**rates):
    return override_settings(
        REST_FRAMEWORK={
            **settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": {**DEFAULT_RATES, **rates},
        }
    )


def registration_payload(number):
    return {
        "email": f"throttle.{number}@example.com",
        "password": DEFAULT_PASSWORD,
        "password2": DEFAULT_PASSWORD,
        "first_name": "Rate",
        "last_name": "Limit",
    }


class ThrottledTestCase(CacheResetAPITestCase):
    def post_wrong_logins(self, times, **headers):
        payload = {"email": DEFAULT_EMAIL, "password": WRONG_PASSWORD}
        return [
            self.client.post(LOGIN_URL, payload, format="json", **headers).status_code
            for _ in range(times)
        ]


# The limit counts requests, not password checks: a fast hasher keeps the dozens of logins
# in these tests from taking seconds each. The account lockout is off so the repeated
# failures against one account reach the throttle; test_login_lockout covers both together.
@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    AXES_ENABLED=False,
)
@override_rates()
class LoginThrottleTests(ThrottledTestCase):
    def setUp(self):
        super().setUp()
        create_user()

    def test_eleventh_login_in_ten_minutes_is_throttled(self):
        statuses = self.post_wrong_logins(11)

        self.assertEqual(statuses[:10], [status.HTTP_401_UNAUTHORIZED] * 10)
        self.assertEqual(statuses[10], status.HTTP_429_TOO_MANY_REQUESTS)

    @override_rates(login="1/10m")
    def test_throttled_response_says_when_to_retry(self):
        self.post_wrong_logins(1)

        response = self.client.post(LOGIN_URL, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertRegex(str(response.data["detail"]), r"available in \d+ seconds?")

    @override_rates(login="1/10m")
    def test_correct_password_is_throttled_too(self):
        self.post_wrong_logins(1)

        response = self.client.post(
            LOGIN_URL,
            {"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @override_rates(login="1/10m")
    def test_login_is_allowed_again_after_the_period(self):
        self.post_wrong_logins(1)
        later = time.time() + TEN_MINUTES + 1

        with mock.patch.object(ScopedRateThrottle, "timer", return_value=later):
            statuses = self.post_wrong_logins(1)

        self.assertEqual(statuses, [status.HTTP_401_UNAUTHORIZED])

    @override_rates(login="2/10m")
    def test_rotating_x_forwarded_for_does_not_bypass_the_limit(self):
        statuses = [
            self.post_wrong_logins(1, HTTP_X_FORWARDED_FOR=f"203.0.113.{number}")[0]
            for number in range(3)
        ]

        self.assertEqual(statuses[2], status.HTTP_429_TOO_MANY_REQUESTS)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    @override_rates(login="2/10m")
    def test_rotating_the_entries_before_the_proxy_does_not_bypass_the_limit(self):
        statuses = [
            self.post_wrong_logins(
                1, HTTP_X_FORWARDED_FOR=f"198.51.100.{number}, 203.0.113.9"
            )[0]
            for number in range(3)
        ]

        self.assertEqual(statuses[2], status.HTTP_429_TOO_MANY_REQUESTS)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    @override_rates(login="2/10m")
    def test_rotating_invalid_entries_does_not_bypass_the_limit(self):
        statuses = [
            self.post_wrong_logins(1, HTTP_X_FORWARDED_FOR=f"garbage-{number}")[0]
            for number in range(3)
        ]

        self.assertEqual(statuses[2], status.HTTP_429_TOO_MANY_REQUESTS)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    @override_rates(login="1/10m")
    def test_clients_behind_the_same_proxy_have_separate_limits(self):
        first = self.post_wrong_logins(1, HTTP_X_FORWARDED_FOR="203.0.113.1")
        second = self.post_wrong_logins(1, HTTP_X_FORWARDED_FOR="203.0.113.2")

        self.assertEqual(first + second, [status.HTTP_401_UNAUTHORIZED] * 2)

    @override_rates(login=None)
    def test_empty_rate_means_no_limit(self):
        statuses = self.post_wrong_logins(11)

        self.assertEqual(statuses, [status.HTTP_401_UNAUTHORIZED] * 11)


@override_rates()
class RegisterThrottleTests(ThrottledTestCase):
    def test_sixth_registration_in_an_hour_is_throttled(self):
        statuses = [
            self.client.post(
                REGISTER_URL, registration_payload(number), format="json"
            ).status_code
            for number in range(6)
        ]

        self.assertEqual(statuses[:5], [status.HTTP_201_CREATED] * 5)
        self.assertEqual(statuses[5], status.HTTP_429_TOO_MANY_REQUESTS)

    @override_rates(login="1/10m")
    def test_login_and_register_have_separate_limits(self):
        self.post_wrong_logins(1)

        response = self.client.post(
            REGISTER_URL, registration_payload(0), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class DefaultThrottleTests(ThrottledTestCase):
    @override_rates(anon="2/m")
    def test_anon_rate_applies_to_endpoints_without_a_scope(self):
        statuses = [
            self.client.post(REFRESH_URL, {"refresh": "x"}, format="json").status_code
            for _ in range(3)
        ]

        self.assertEqual(statuses[2], status.HTTP_429_TOO_MANY_REQUESTS)

    def test_rates_are_configured_for_every_scope(self):
        rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]

        self.assertEqual(set(rates), set(DEFAULT_RATES))

from unittest import mock

from django.db import OperationalError
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from security.models import AuditLog
from security.tests.api_test_case import CacheResetAPITestCase
from security.tests.test_throttling import override_rates

HEALTH_URL = "/api/v1/health/"
HEALTHY = {"status": "ok", "database": "ok"}
UNHEALTHY = {"status": "error", "database": "error"}
CONNECTION_ERROR = "connection to server failed: password=not-for-the-log"


def database_down():
    return mock.patch(
        "core.health.connection.cursor", side_effect=OperationalError(CONNECTION_ERROR)
    )


class HealthTests(CacheResetAPITestCase):
    def test_route_is_named_health(self):
        self.assertEqual(reverse("health"), HEALTH_URL)

    def test_answers_ok_to_anonymous_clients(self):
        response = self.client.get(HEALTH_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), HEALTHY)

    def test_ignores_the_authorization_header(self):
        for header in ("Bearer not-a-token", "Basic Zm9vOmJhcg=="):
            with self.subTest(header=header):
                response = self.client.get(HEALTH_URL, HTTP_AUTHORIZATION=header)

                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_answers_head_requests(self):
        response = self.client.head(HEALTH_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_is_never_cached(self):
        response = self.client.get(HEALTH_URL)

        self.assertIn("no-store", response["Cache-Control"])

    def test_rejects_writes_with_the_api_error_format(self):
        for method in ("post", "put", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(HEALTH_URL)

                self.assertEqual(
                    response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
                )
                self.assertEqual(response.json()["code"], "method_not_allowed")

    def test_answers_503_when_the_database_is_down(self):
        with database_down(), self.assertLogs("core.health", "ERROR") as logs:
            with self.assertLogs("django.request", "ERROR"):
                response = self.client.get(HEALTH_URL)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.json(), UNHEALTHY)
        self.assertNotIn("not-for-the-log", "\n".join(logs.output))

    def test_does_not_reveal_versions_or_hosts(self):
        response = self.client.get(HEALTH_URL)

        self.assertEqual(set(response.json()), {"status", "database"})

    @override_rates(anon="1/m")
    def test_is_not_throttled(self):
        statuses = [self.client.get(HEALTH_URL).status_code for _ in range(3)]

        self.assertEqual(statuses, [status.HTTP_200_OK] * 3)

    def test_reads_are_not_audited(self):
        self.client.get(HEALTH_URL)

        self.assertFalse(AuditLog.objects.filter(path=HEALTH_URL).exists())


# In staging and prod plain HTTP is redirected to HTTPS, but an orchestrator probes the
# container over HTTP: the health route is the one exception.
@override_settings(SECURE_SSL_REDIRECT=True, ALLOWED_HOSTS=["api.example.com"])
class HealthBehindHttpsRedirectTests(CacheResetAPITestCase):
    def test_health_answers_over_plain_http(self):
        response = self.client.get(HEALTH_URL, HTTP_HOST="api.example.com")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_other_routes_are_still_redirected(self):
        response = self.client.get(reverse("security:me"), HTTP_HOST="api.example.com")

        self.assertEqual(response.status_code, status.HTTP_301_MOVED_PERMANENTLY)

    def test_unknown_hosts_are_still_rejected(self):
        with self.assertLogs("django.security.DisallowedHost", "ERROR"):
            response = self.client.get(HEALTH_URL, HTTP_HOST="10.0.0.12")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

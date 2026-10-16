from django.db import connection
from django.test import TestCase


class AuditLogIndexTests(TestCase):
    def index_columns(self):
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(
                cursor, "security_auditlog"
            )
        return {
            name: spec["columns"] for name, spec in constraints.items() if spec["index"]
        }

    def test_indexes_the_timestamp(self):
        self.assertEqual(self.index_columns()["auditlog_timestamp_idx"], ["timestamp"])

    def test_indexes_the_user_and_timestamp_together(self):
        self.assertEqual(
            self.index_columns()["auditlog_user_timestamp_idx"],
            ["user_id", "timestamp"],
        )

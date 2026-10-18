import json
import logging
from datetime import datetime

from django.test import SimpleTestCase

from core.log_formatters import JsonFormatter


def build_record(message="Something happened", extra=None, exc_info=None):
    record = logging.LogRecord(
        "security.signals", logging.WARNING, __file__, 10, message, None, exc_info
    )
    for name, value in (extra or {}).items():
        setattr(record, name, value)
    return record


def format_as_json(record):
    return json.loads(JsonFormatter().format(record))


class JsonFormatterTests(SimpleTestCase):
    def test_writes_a_single_json_line(self):
        output = JsonFormatter().format(build_record("two\nlines"))

        self.assertNotIn("\n", output)
        self.assertEqual(json.loads(output)["message"], "two\nlines")

    def test_includes_level_logger_and_message(self):
        line = format_as_json(build_record())

        self.assertEqual(line["level"], "WARNING")
        self.assertEqual(line["logger"], "security.signals")
        self.assertEqual(line["message"], "Something happened")

    def test_timestamp_is_iso_8601_in_utc(self):
        timestamp = format_as_json(build_record())["timestamp"]

        self.assertTrue(timestamp.endswith("Z"))
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    def test_adds_the_extra_fields(self):
        line = format_as_json(
            build_record(extra={"event": "login_failed", "ip": "203.0.113.5"})
        )

        self.assertEqual(line["event"], "login_failed")
        self.assertEqual(line["ip"], "203.0.113.5")

    def test_leaves_out_the_record_internals(self):
        line = format_as_json(build_record())

        for internal in ("args", "msg", "pathname", "exc_info", "stack_info"):
            self.assertNotIn(internal, line)

    def test_adds_the_traceback_of_an_exception(self):
        try:
            raise ValueError("boom")
        except ValueError as error:
            exc_info = (type(error), error, error.__traceback__)

        line = format_as_json(build_record(exc_info=exc_info))

        self.assertIn("ValueError: boom", line["exception"])

    def test_values_json_cannot_encode_become_text(self):
        line = format_as_json(build_record(extra={"when": datetime(2026, 1, 2)}))

        self.assertEqual(line["when"], "2026-01-02 00:00:00")

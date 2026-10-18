from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from core.logging_config import build_logging_config, parse_log_format, parse_log_level


class LogLevelTests(SimpleTestCase):
    def test_accepts_the_standard_levels_in_any_case(self):
        for raw, expected in (
            ("info", "INFO"),
            ("Warning", "WARNING"),
            ("DEBUG", "DEBUG"),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(parse_log_level(raw), expected)

    def test_rejects_an_unknown_level_listing_the_valid_ones(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "LOG_LEVEL='verbose'"):
            parse_log_level("verbose")

        with self.assertRaisesMessage(ImproperlyConfigured, "CRITICAL"):
            parse_log_level("verbose")


class LogFormatTests(SimpleTestCase):
    def test_accepts_text_and_json(self):
        for raw, expected in (("text", "text"), ("JSON", "json")):
            with self.subTest(raw=raw):
                self.assertEqual(parse_log_format(raw), expected)

    def test_rejects_an_unknown_format(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "LOG_FORMAT='xml'"):
            parse_log_format("xml")


class LoggingConfigTests(SimpleTestCase):
    def test_sends_every_logger_to_the_console(self):
        config = build_logging_config("WARNING", "text")

        self.assertEqual(config["root"], {"handlers": ["console"], "level": "WARNING"})
        self.assertEqual(
            config["handlers"]["console"]["class"], "logging.StreamHandler"
        )
        self.assertFalse(config["disable_existing_loggers"])

    def test_picks_the_formatter_of_the_format(self):
        for log_format, formatter_class in (
            ("text", "logging.Formatter"),
            ("json", "core.log_formatters.JsonFormatter"),
        ):
            with self.subTest(log_format=log_format):
                config = build_logging_config("INFO", log_format)
                formatter = config["handlers"]["console"]["formatter"]

                self.assertEqual(config["formatters"][formatter]["()"], formatter_class)

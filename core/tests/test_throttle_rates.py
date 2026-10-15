from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from core.throttle_rates import InvalidRateError, parse_rate


class ParseRateTests(SimpleTestCase):
    def test_parses_any_multiple_of_the_unit(self):
        cases = {
            "10/10m": (10, 600),
            "1/s": (1, 1),
            "100/6h": (100, 21600),
            "5/h": (5, 3600),
            "3/1m": (3, 60),
            "1000/2d": (1000, 172800),
        }

        for rate, expected in cases.items():
            with self.subTest(rate=rate):
                self.assertEqual(parse_rate(rate), expected)

    def test_empty_rate_means_no_limit(self):
        self.assertEqual(parse_rate(""), (None, None))
        self.assertEqual(parse_rate(None), (None, None))

    def test_rejects_malformed_rates(self):
        for rate in ("10", "/m", "10/0m", "10/x", "-1/m", "10/1.5h", "abc/m"):
            with self.subTest(rate=rate):
                with self.assertRaisesMessage(InvalidRateError, repr(rate)):
                    parse_rate(rate)

    def test_rejects_the_long_drf_units(self):
        for rate in ("10/minute", "10/hour", "10/day"):
            with self.subTest(rate=rate):
                with self.assertRaises(InvalidRateError):
                    parse_rate(rate)

    def test_the_error_stops_django_from_starting(self):
        self.assertTrue(issubclass(InvalidRateError, ImproperlyConfigured))

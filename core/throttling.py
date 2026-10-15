from django.core.exceptions import ImproperlyConfigured
from rest_framework import throttling
from rest_framework.settings import api_settings

from core.throttle_rates import parse_rate


class ConfigurableRateMixin:
    """Accepts multiples of the period (10/10m) and reads the rate on every request.

    DRF copies the rates into a class attribute at import time, so a rate changed later
    (override_settings in tests) never reaches its throttles.
    """

    def get_rate(self):
        rates = api_settings.DEFAULT_THROTTLE_RATES
        if self.scope not in rates:
            raise ImproperlyConfigured(
                f"No throttle rate set for scope {self.scope!r}."
            )
        return rates[self.scope]

    def parse_rate(self, rate):
        return parse_rate(rate)


class AnonRateThrottle(ConfigurableRateMixin, throttling.AnonRateThrottle):
    pass


class UserRateThrottle(ConfigurableRateMixin, throttling.UserRateThrottle):
    pass


class ScopedRateThrottle(ConfigurableRateMixin, throttling.ScopedRateThrottle):
    pass

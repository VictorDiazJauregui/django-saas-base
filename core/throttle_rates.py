import re

from django.core.exceptions import ImproperlyConfigured

# Kept free of DRF imports: settings.py parses the rates while Django is still loading.
UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
RATE_PATTERN = re.compile(r"(?P<requests>\d+)/(?P<multiplier>\d*)(?P<unit>[smhd])")


class InvalidRateError(ImproperlyConfigured):
    def __init__(self, rate):
        super().__init__(
            f"Invalid throttle rate {rate!r}. Use <requests>/<period> with the period "
            "in s, m, h or d and an optional multiple, such as 10/m, 10/10m or 100/6h. "
            "Leave it empty for no limit."
        )


def parse_rate(rate):
    if not rate:
        return None, None
    match = RATE_PATTERN.fullmatch(rate)
    if match is None:
        raise InvalidRateError(rate)
    multiplier = int(match["multiplier"] or 1)
    if multiplier == 0:
        raise InvalidRateError(rate)
    return int(match["requests"]), multiplier * UNIT_SECONDS[match["unit"]]


def validate_rate(rate):
    parse_rate(rate)
    return rate or None

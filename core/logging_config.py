from django.core.exceptions import ImproperlyConfigured

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
LOG_FORMATS = ("text", "json")
TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def parse_choice(name, raw_value, choices):
    value = raw_value.strip()
    matches = [choice for choice in choices if choice.lower() == value.lower()]
    if not matches:
        raise ImproperlyConfigured(
            f"{name}={raw_value!r} is not valid. Use one of: {', '.join(choices)}."
        )
    return matches[0]


def parse_log_level(raw_value):
    return parse_choice("LOG_LEVEL", raw_value, LOG_LEVELS)


def parse_log_format(raw_value):
    return parse_choice("LOG_FORMAT", raw_value, LOG_FORMATS)


# Django applies its own DEFAULT_LOGGING first; its "django" logger is reset here so its
# records reach the console once, through the root logger and the chosen format.
def build_logging_config(level, log_format):
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "text": {"()": "logging.Formatter", "format": TEXT_FORMAT},
            "json": {"()": "core.log_formatters.JsonFormatter"},
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler", "formatter": log_format}
        },
        "root": {"handlers": ["console"], "level": level},
        "loggers": {"django": {"handlers": [], "level": level, "propagate": True}},
    }

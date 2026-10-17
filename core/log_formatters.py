import json
import logging
from datetime import UTC, datetime

# Attributes every LogRecord has: anything else on a record came from extra={...}.
STANDARD_RECORD_ATTRIBUTES = frozenset(
    vars(logging.LogRecord("", logging.INFO, "", 0, "", None, None))
) | {"message", "asctime"}


def format_timestamp(created):
    moment = datetime.fromtimestamp(created, UTC)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def read_extra_fields(record):
    return {
        name: value
        for name, value in vars(record).items()
        if name not in STANDARD_RECORD_ATTRIBUTES
    }


# One JSON object per line, as Loki, Datadog and most log collectors expect. Values JSON
# can't encode are written as text instead of breaking the line.
class JsonFormatter(logging.Formatter):
    def format(self, record):
        line = {
            "timestamp": format_timestamp(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **read_extra_fields(record),
        }
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str, ensure_ascii=False)

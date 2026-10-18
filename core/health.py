import logging

from django.db import DatabaseError, connection

logger = logging.getLogger(__name__)

HEALTHY = "ok"
UNHEALTHY = "error"


# Only the exception class reaches the log: its message can carry the host, the port or
# the database user.
def check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError as error:
        logger.error(
            "The database did not answer the health check: %s.", type(error).__name__
        )
        return False
    return True


def describe_health():
    database = HEALTHY if check_database() else UNHEALTHY
    return {"status": database, "database": database}

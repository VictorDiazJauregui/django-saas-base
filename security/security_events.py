import logging

from core.client_ip import get_client_ip

from .login_lockout import get_lockout_username

logger = logging.getLogger(__name__)


def describe_user(user):
    return str(user.pk) if user is not None else None


# The email is logged so an attack on one account can be traced; the password never is, not
# even masked.
def log_failed_login(request, credentials):
    email = get_lockout_username(request, credentials)
    ip = get_client_ip(request) if request is not None else None
    path = request.path if request is not None else None
    fields = {"event": "login_failed", "email": email, "ip": ip, "path": path}
    logger.warning("Failed login for %s from %s.", email, ip, extra=fields)


def log_lockout(email, ip):
    fields = {"event": "account_locked_out", "email": email, "ip": ip}
    logger.warning(
        "Login refused: %s is locked out (from %s).", email, ip, extra=fields
    )


def log_token_revoked(user, reason):
    fields = {
        "event": "token_revoked",
        "user_id": describe_user(user),
        "reason": reason,
    }
    logger.info("Revoked a refresh token of user %s.", fields["user_id"], extra=fields)


def log_tokens_revoked(user, count, reason):
    user_id = describe_user(user)
    fields = {
        "event": "tokens_revoked",
        "user_id": user_id,
        "count": count,
        "reason": reason,
    }
    logger.info("Revoked %s refresh tokens of user %s.", count, user_id, extra=fields)

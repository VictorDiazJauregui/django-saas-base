from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

DEVELOPMENT_ENVIRONMENTS = ("local", "ci")
DEPLOYED_ENVIRONMENTS = ("staging", "prod")
VALID_ENVIRONMENTS = DEVELOPMENT_ENVIRONMENTS + DEPLOYED_ENVIRONMENTS
WILDCARD_HOST = "*"
LINK_MARKERS = ("{uid}", "{token}")
LINK_SCHEMES = ("http", "https")


def validate_environment(name):
    if name in VALID_ENVIRONMENTS:
        return name
    raise ImproperlyConfigured(
        f"ENVIRONMENT={name!r} is not valid. Use one of: {', '.join(VALID_ENVIRONMENTS)}."
    )


def is_deployed(environment):
    return environment in DEPLOYED_ENVIRONMENTS


def validate_debug(debug, environment):
    if debug and is_deployed(environment):
        raise ImproperlyConfigured(
            f"DEBUG=True is only allowed when ENVIRONMENT is local or ci, not {environment!r}."
        )
    return debug


def default_allowed_hosts(environment, debug):
    if is_deployed(environment):
        return []
    return [WILDCARD_HOST] if debug else ["localhost"]


def validate_allowed_hosts(hosts, environment):
    if not is_deployed(environment):
        return hosts
    if not hosts or WILDCARD_HOST in hosts:
        raise ImproperlyConfigured(
            "ALLOWED_HOSTS must list the domains that serve this project, without '*', "
            "when ENVIRONMENT is staging or prod. Example: ALLOWED_HOSTS=api.example.com"
        )
    return hosts


def matches_every_origin(origin):
    return origin.split("://")[-1] == WILDCARD_HOST


def validate_csrf_trusted_origins(origins, environment):
    if not is_deployed(environment):
        return origins
    if any(matches_every_origin(origin) for origin in origins):
        raise ImproperlyConfigured(
            "CSRF_TRUSTED_ORIGINS can't trust every origin when ENVIRONMENT is staging "
            "or prod. List each origin with its scheme: https://admin.example.com"
        )
    return origins


# Both options are off by default on purpose (preload is close to irreversible for a
# domain), so their deploy warnings are noise until someone turns them on.
def silenced_hsts_checks(include_subdomains, preload):
    silenced = []
    if not include_subdomains:
        silenced.append("security.W005")
    if not preload:
        silenced.append("security.W021")
    return silenced


def validate_trusted_proxy_count(count):
    if count < 0:
        raise ImproperlyConfigured(
            f"TRUSTED_PROXY_COUNT={count} is not valid. Use 0 without a proxy, or the "
            "number of proxies in front of Django that append to X-Forwarded-For."
        )
    return count


def parse_int_at_least(name, raw_value, minimum):
    try:
        value = int(raw_value)
    except ValueError:
        value = minimum - 1
    if value < minimum:
        raise ImproperlyConfigured(
            f"{name}={raw_value!r} is not valid. Use a whole number of {minimum} or more."
        )
    return value


def parse_positive_int(name, raw_value):
    return parse_int_at_least(name, raw_value, minimum=1)


def parse_non_negative_int(name, raw_value):
    return parse_int_at_least(name, raw_value, minimum=0)


# The words django-environ reads as booleans, so every flag accepts the same values.
BOOLEAN_WORDS = {
    **dict.fromkeys(("true", "on", "ok", "y", "yes", "1"), True),
    **dict.fromkeys(("false", "off", "n", "no", "0"), False),
}


# Empty means "use the default", so a value copied empty from .env.example keeps it.
def parse_optional_bool(name, raw_value, default):
    if not raw_value.strip():
        return default
    value = BOOLEAN_WORDS.get(raw_value.strip().lower())
    if value is None:
        raise ImproperlyConfigured(
            f"{name}={raw_value!r} is not valid. Use True or False, or leave it empty."
        )
    return value


def validate_page_sizes(page_size, max_page_size):
    if page_size > max_page_size:
        raise ImproperlyConfigured(
            f"API_PAGE_SIZE={page_size} can't be larger than "
            f"API_MAX_PAGE_SIZE={max_page_size}."
        )
    return page_size


def validate_frontend_link_url(name, url):
    parts = urlsplit(url)
    if parts.scheme not in LINK_SCHEMES or not parts.hostname:
        raise ImproperlyConfigured(
            f"{name}={url!r} is not valid. Use the absolute URL of the frontend page, "
            "such as https://app.example.com/reset-password?uid={uid}&token={token}."
        )
    missing_markers = [marker for marker in LINK_MARKERS if marker not in url]
    if missing_markers:
        raise ImproperlyConfigured(
            f"{name} must contain {{uid}} and {{token}}, which the API replaces with the "
            f"values the frontend sends back. Missing: {', '.join(missing_markers)}."
        )
    return url


def validate_optional_frontend_link_url(name, url, required):
    if not url and not required:
        return ""
    return validate_frontend_link_url(name, url)


LOCKOUT_FIELDS = ("username", "ip_address", "user_agent")


def parse_lockout_combination(raw_combination):
    fields = [field.strip() for field in raw_combination.split("+")]
    if not all(field in LOCKOUT_FIELDS for field in fields):
        raise ImproperlyConfigured(
            f"AXES_LOCKOUT_PARAMETERS has {raw_combination!r}. Join fields with '+' and "
            f"separate combinations with ',', using only: {', '.join(LOCKOUT_FIELDS)}."
        )
    return fields if len(fields) > 1 else fields[0]


# axes takes a list where a plain field locks on its own and a list of fields locks on
# their combination: "username+ip_address,user_agent" -> [["username", "ip_address"], "user_agent"].
def parse_lockout_parameters(raw_value):
    return [parse_lockout_combination(part) for part in raw_value.split(",")]


def validate_totp_encryption_key(key, enabled):
    if not enabled:
        return key
    try:
        Fernet(key)
    except ValueError as error:
        raise ImproperlyConfigured(
            "TOTP_ENABLED=True needs TOTP_ENCRYPTION_KEY, a Fernet key. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        ) from error
    return key

from django.core.exceptions import ImproperlyConfigured

DEVELOPMENT_ENVIRONMENTS = ("local", "ci")
DEPLOYED_ENVIRONMENTS = ("staging", "prod")
VALID_ENVIRONMENTS = DEVELOPMENT_ENVIRONMENTS + DEPLOYED_ENVIRONMENTS
WILDCARD_HOST = "*"


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


def parse_positive_int(name, raw_value):
    try:
        value = int(raw_value)
    except ValueError:
        value = 0
    if value < 1:
        raise ImproperlyConfigured(
            f"{name}={raw_value!r} is not valid. Use a whole number greater than 0."
        )
    return value


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

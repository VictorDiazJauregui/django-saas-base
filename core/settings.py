"""
Django settings for the saas_boilerplate project.
"""

import os
from datetime import timedelta
from importlib.util import find_spec
from pathlib import Path

import environ
from django.utils.translation import gettext_lazy as _

from core.email_provider import (
    build_provider_backend,
    read_anymail_settings,
    validate_email_provider,
)
from core.environment import (
    default_allowed_hosts,
    is_deployed,
    parse_lockout_parameters,
    parse_non_negative_int,
    parse_optional_bool,
    parse_positive_int,
    silenced_hsts_checks,
    validate_allowed_hosts,
    validate_csrf_trusted_origins,
    validate_debug,
    validate_environment,
    validate_frontend_link_url,
    validate_optional_frontend_link_url,
    validate_page_sizes,
    validate_totp_encryption_key,
    validate_trusted_proxy_count,
)
from core.logging_config import build_logging_config, parse_log_format, parse_log_level
from core.throttle_rates import validate_rate

# Initialize django-environ
env = environ.Env()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Take environment variables from .env file
environ.Env.read_env(BASE_DIR / ".env")

# --- Core Settings ---
ENVIRONMENT = validate_environment(env.str("ENVIRONMENT"))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

DEBUG = validate_debug(env.bool("DEBUG", default=False), ENVIRONMENT)

ALLOWED_HOSTS = validate_allowed_hosts(
    env.list("ALLOWED_HOSTS", default=default_allowed_hosts(ENVIRONMENT, DEBUG)),
    ENVIRONMENT,
)

APP_PORT = env.str("APP_PORT", default="8000")


# --- Application Definition ---
INSTALLED_APPS = [
    # Listed first so its runserver command overrides the staticfiles one.
    "core",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "axes",
    "corsheaders",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    # Local apps
    "security.apps.SecurityConfig",
]

OPTIONAL_DEVELOPMENT_APPS = ["django_extensions"]
INSTALLED_APPS += [app for app in OPTIONAL_DEVELOPMENT_APPS if find_spec(app)]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Right after SecurityMiddleware, as whitenoise asks: it serves the static files itself.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # Before CommonMiddleware, as django-cors-headers asks: it answers preflights early.
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",  # i18n
    # CommonMiddleware, but a missing trailing slash under /api/ gets a JSON error, not a redirect.
    "core.middleware.ApiCommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "security.middleware.AuditMiddleware",  # Audit log middleware
    # Last, as axes asks: it turns a lockout flagged during the request into the 429.
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"


# --- Database ---
# https://docs.djangoproject.com/en/stable/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
        # Seconds a connection stays open for the next request; 0 closes it after each one.
        "CONN_MAX_AGE": parse_non_negative_int(
            "DB_CONN_MAX_AGE", env.str("DB_CONN_MAX_AGE", default="60")
        ),
        "CONN_HEALTH_CHECKS": True,
    }
}


# --- Password Validation ---
# https://docs.djangoproject.com/en/stable/ref/settings/#auth-password-validators
PASSWORD_MIN_LENGTH = env.int("PASSWORD_MIN_LENGTH", default=8)
PASSWORD_REQUIRED_CHARACTER_CLASSES = [
    name
    for name in ("uppercase", "lowercase", "digit", "symbol")
    if env.bool(f"PASSWORD_REQUIRE_{name.upper()}", default=True)
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": PASSWORD_MIN_LENGTH},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {
        "NAME": "security.password_validation.CharacterClassValidator",
        "OPTIONS": {"required_classes": PASSWORD_REQUIRED_CHARACTER_CLASSES},
    },
]

# --- Custom User Model ---
AUTH_USER_MODEL = "security.User"

# axes checks the lockout before any other backend tries the password.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "security.authentication.VerifiedEmailModelBackend",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Internationalization (i18n) ---
# https://docs.djangoproject.com/en/stable/topics/i18n/
LANGUAGE_CODE = "en-us"
LANGUAGES = [
    ("en", _("English")),
    ("es", _("Spanish")),
]
LOCALE_PATHS = [
    BASE_DIR / "locale",
]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# --- Static files (CSS, JavaScript, Images) ---
# https://docs.djangoproject.com/en/stable/howto/static-files/
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# The hashed, compressed files need collectstatic first, which local work and the tests
# never run: only staging and prod use them.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if is_deployed(ENVIRONMENT)
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}
# Without collectstatic there is no STATIC_ROOT: outside staging and prod, whitenoise looks
# the files up on each request instead of warning that the directory is missing.
WHITENOISE_AUTOREFRESH = not is_deployed(ENVIRONMENT)


# --- Logging ---
# Everything goes to the console: text for local work, json for log collectors.
LOGGING = build_logging_config(
    parse_log_level(env.str("LOG_LEVEL", default="INFO")),
    parse_log_format(env.str("LOG_FORMAT", default="text")),
)


# --- Cache ---
# Throttling counts requests here. locmem is per process: use Redis with several workers.
CACHES = {"default": env.cache_url("CACHE_URL", default="locmemcache://")}


# --- Client IP ---
# Shared by the audit log and the throttling through core.client_ip.get_client_ip.
TRUSTED_PROXY_COUNT = validate_trusted_proxy_count(
    env.int("TRUSTED_PROXY_COUNT", default=0)
)


# --- Audit log ---
AUDIT_EXTRA_SENSITIVE_KEYS = env.list("AUDIT_EXTRA_SENSITIVE_KEYS", default=[])
AUDIT_PAYLOAD_MAX_BYTES = parse_non_negative_int(
    "AUDIT_PAYLOAD_MAX_BYTES", env.str("AUDIT_PAYLOAD_MAX_BYTES", default="65536")
)


# --- Email ---
# One URL configures any SMTP provider; empty or missing prints the emails to the console.
# Lowercase so the parsed URL, password included, does not become a setting of its own.
email_url = env.str("EMAIL_URL", default="")
email_url_settings = env.email_url_config(email_url or "consolemail://")
# A provider name sends through its HTTP API with anymail instead of SMTP.
EMAIL_PROVIDER = validate_email_provider(
    env.str("EMAIL_PROVIDER", default=""), email_url
)
EMAIL_BACKEND = (
    build_provider_backend(EMAIL_PROVIDER)
    if EMAIL_PROVIDER
    else email_url_settings["EMAIL_BACKEND"]
)
EMAIL_HOST = email_url_settings["EMAIL_HOST"] or "localhost"
EMAIL_PORT = email_url_settings["EMAIL_PORT"] or 25
EMAIL_HOST_USER = email_url_settings["EMAIL_HOST_USER"] or ""
EMAIL_HOST_PASSWORD = email_url_settings["EMAIL_HOST_PASSWORD"] or ""
EMAIL_USE_TLS = email_url_settings.get("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = email_url_settings.get("EMAIL_USE_SSL", False)
# Without a timeout, an SMTP server that stops answering blocks the sender forever.
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="webmaster@localhost")
# Every ANYMAIL_* variable, without the prefix. The timeout stays the SMTP one: a text value
# from the environment would break the HTTP client.
ANYMAIL = {**read_anymail_settings(os.environ), "REQUESTS_TIMEOUT": EMAIL_TIMEOUT}
EMAIL_SEND_IN_BACKGROUND = True

# --- CORS ---
# Empty means no other origin can call the API from a browser. Every origin needs its
# scheme: django-cors-headers refuses to start with "*" or a bare domain.
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_URLS_REGEX = r"^/api/.*$"
# Browsers hide every other response header from a different origin.
CORS_EXPOSE_HEADERS = ["Retry-After"]

# --- Registration ---
# False closes POST /api/v1/auth/register/; the admin and create_admin_auto still add users.
ALLOW_PUBLIC_REGISTRATION = env.bool("ALLOW_PUBLIC_REGISTRATION", default=True)

# --- API keys ---
# True lets other servers authenticate with "Authorization: Api-Key <key>". Keys are created
# in the admin and act as the user they belong to.
API_KEYS_ENABLED = env.bool("API_KEYS_ENABLED", default=False)

# --- Two-factor authentication ---
# True lets each user turn on a second factor with an authenticator app. The secrets are
# encrypted with their own key, so rotating SECRET_KEY doesn't lock anyone out.
TOTP_ENABLED = env.bool("TOTP_ENABLED", default=False)
TOTP_ENCRYPTION_KEY = validate_totp_encryption_key(
    env.str("TOTP_ENCRYPTION_KEY", default=""), TOTP_ENABLED
)
# The name the authenticator app shows next to the account. Empty shows only the email.
TOTP_ISSUER = env.str("TOTP_ISSUER", default="")

# --- Roles ---
# The roles sync_roles applies as Django groups. Point it at your own module to declare them.
ROLE_DEFINITIONS = "core.roles.ROLES"

# --- Account emails ---
# The API has no pages: the emails link to the frontend, which sends {uid} and {token} back.
FRONTEND_PASSWORD_RESET_URL = validate_frontend_link_url(
    "FRONTEND_PASSWORD_RESET_URL", env.str("FRONTEND_PASSWORD_RESET_URL", default="")
)
PASSWORD_RESET_TIMEOUT = 60 * parse_positive_int(
    "PASSWORD_RESET_TIMEOUT_MINUTES",
    env.str("PASSWORD_RESET_TIMEOUT_MINUTES", default="60"),
)
# True makes a public registration log in only after following the link of its email.
REQUIRE_EMAIL_VERIFICATION = env.bool("REQUIRE_EMAIL_VERIFICATION", default=False)
FRONTEND_EMAIL_VERIFICATION_URL = validate_optional_frontend_link_url(
    "FRONTEND_EMAIL_VERIFICATION_URL",
    env.str("FRONTEND_EMAIL_VERIFICATION_URL", default=""),
    required=REQUIRE_EMAIL_VERIFICATION,
)
EMAIL_VERIFICATION_TIMEOUT = 3600 * parse_positive_int(
    "EMAIL_VERIFICATION_TIMEOUT_HOURS",
    env.str("EMAIL_VERIFICATION_TIMEOUT_HOURS", default="24"),
)

# --- Django Rest Framework (DRF) ---
API_MAX_PAGE_SIZE = parse_positive_int(
    "API_MAX_PAGE_SIZE", env.str("API_MAX_PAGE_SIZE", default="100")
)
API_PAGE_SIZE = validate_page_sizes(
    parse_positive_int("API_PAGE_SIZE", env.str("API_PAGE_SIZE", default="20")),
    API_MAX_PAGE_SIZE,
)

# An empty rate means no limit for that scope.
THROTTLE_RATE_DEFAULTS = {
    "anon": "",
    "user": "",
    "login": "10/10m",
    "register": "5/h",
    "password": "5/h",
    "verify_email": "5/h",
    "mfa": "5/10m",
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "security.authentication.ApiKeyAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_THROTTLE_CLASSES": (
        "core.throttling.AnonRateThrottle",
        "core.throttling.UserRateThrottle",
        "core.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        scope: validate_rate(env.str(f"THROTTLE_{scope.upper()}_RATE", default=rate))
        for scope, rate in THROTTLE_RATE_DEFAULTS.items()
    },
    # Without it DRF identifies clients by the whole X-Forwarded-For header, which the
    # client controls: rotating it would skip every limit.
    "NUM_PROXIES": TRUSTED_PROXY_COUNT,
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    # A frontend only needs JSON; the browsable API stays for local work with DEBUG=True.
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",)
    + (("rest_framework.renderers.BrowsableAPIRenderer",) if DEBUG else ()),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.ConfigurablePageNumberPagination",
    "PAGE_SIZE": API_PAGE_SIZE,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# --- API docs ---
# True serves /api/schema/ and /api/docs/ to anyone; False only to active staff users, logged
# in to the admin or with a token. Empty keeps the default: open in local and ci only.
API_DOCS_ENABLED = parse_optional_bool(
    "API_DOCS_ENABLED",
    env.str("API_DOCS_ENABLED", default=""),
    default=not is_deployed(ENVIRONMENT),
)
SPECTACULAR_SETTINGS = {
    "TITLE": "API",
    "VERSION": "v1",
    "SERVE_INCLUDE_SCHEMA": False,
    # Separate request and response types, so write-only fields such as passwords don't
    # show up in the response types a frontend generates.
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
}

# --- JWT ---
# Each refresh returns a new refresh token and blacklists the one used, so a stolen
# refresh token stops working as soon as either side uses it.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=parse_positive_int(
            "JWT_ACCESS_MINUTES", env.str("JWT_ACCESS_MINUTES", default="5")
        )
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=parse_positive_int(
            "JWT_REFRESH_DAYS", env.str("JWT_REFRESH_DAYS", default="1")
        )
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    # An empty JWT_SIGNING_KEY in .env means "not set", not an empty key.
    "SIGNING_KEY": env.str("JWT_SIGNING_KEY", default="") or SECRET_KEY,
    "TOKEN_REFRESH_SERIALIZER": "security.serializers.ExistingUserTokenRefreshSerializer",
}

# --- Account lockout (django-axes) ---
# Failed logins are counted per account and client IP, in the API and in the admin.
AXES_FAILURE_LIMIT = parse_positive_int(
    "AXES_FAILURE_LIMIT", env.str("AXES_FAILURE_LIMIT", default="5")
)
AXES_COOLOFF_TIME = timedelta(
    minutes=parse_positive_int(
        "AXES_COOLOFF_MINUTES", env.str("AXES_COOLOFF_MINUTES", default="15")
    )
)
AXES_LOCKOUT_PARAMETERS = parse_lockout_parameters(
    env.str("AXES_LOCKOUT_PARAMETERS", default="username+ip_address")
)
AXES_USERNAME_FORM_FIELD = "email"
AXES_USERNAME_CALLABLE = "security.login_lockout.get_lockout_username"
AXES_LOCKOUT_CALLABLE = "security.login_lockout.render_admin_lockout"
AXES_RESET_ON_SUCCESS = True
# Same client IP as the audit log and the throttling.
AXES_CLIENT_IP_CALLABLE = "core.client_ip.get_client_ip"

# --- HTTPS and proxies ---
# staging and prod only serve HTTPS; local and ci keep Django's plain HTTP defaults.
DEPLOYED = is_deployed(ENVIRONMENT)
SECURE_SSL_REDIRECT = DEPLOYED
# Orchestrators and load balancers probe the container over plain HTTP.
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]
SESSION_COOKIE_SECURE = DEPLOYED
CSRF_COOKIE_SECURE = DEPLOYED
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=3600) if DEPLOYED else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False
)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
SILENCED_SYSTEM_CHECKS = silenced_hsts_checks(
    SECURE_HSTS_INCLUDE_SUBDOMAINS, SECURE_HSTS_PRELOAD
)

if env.bool("USE_X_FORWARDED_PROTO", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_TRUSTED_ORIGINS = validate_csrf_trusted_origins(
    env.list("CSRF_TRUSTED_ORIGINS", default=[]), ENVIRONMENT
)

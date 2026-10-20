import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STRONG_SECRET_KEY = "test-only-secret-key-for-the-production-settings-0123456789"

# Settings are read once, at import time, so each scenario runs in its own process.
# Every variable the settings read is set here: a developer's .env only fills in what is
# missing, so leaving one out would let the local .env leak into the scenario.
PRODUCTION_ENVIRONMENT = {
    "ENVIRONMENT": "prod",
    "DEBUG": "False",
    "SECRET_KEY": STRONG_SECRET_KEY,
    "ALLOWED_HOSTS": "api.example.com",
    "CSRF_TRUSTED_ORIGINS": "",
    "SECURE_HSTS_SECONDS": "3600",
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": "False",
    "SECURE_HSTS_PRELOAD": "False",
    "USE_X_FORWARDED_PROTO": "False",
    "TRUSTED_PROXY_COUNT": "0",
    "AUDIT_EXTRA_SENSITIVE_KEYS": "",
    "AUDIT_PAYLOAD_MAX_BYTES": "65536",
    "CACHE_URL": "locmemcache://",
    "THROTTLE_ANON_RATE": "",
    "THROTTLE_USER_RATE": "",
    "THROTTLE_LOGIN_RATE": "10/10m",
    "THROTTLE_REGISTER_RATE": "5/h",
    "THROTTLE_PASSWORD_RATE": "5/h",
    "THROTTLE_VERIFY_EMAIL_RATE": "5/h",
    "THROTTLE_MFA_RATE": "5/10m",
    "JWT_ACCESS_MINUTES": "5",
    "JWT_REFRESH_DAYS": "1",
    "JWT_SIGNING_KEY": "",
    "AXES_FAILURE_LIMIT": "5",
    "AXES_COOLOFF_MINUTES": "15",
    "AXES_LOCKOUT_PARAMETERS": "username+ip_address",
    "EMAIL_URL": "smtp+tls://smtp.example.com:587",
    "EMAIL_PROVIDER": "",
    "DEFAULT_FROM_EMAIL": "webmaster@localhost",
    "FRONTEND_PASSWORD_RESET_URL": "https://app.example.com/reset-password?uid={uid}&token={token}",
    "PASSWORD_RESET_TIMEOUT_MINUTES": "60",
    "REQUIRE_EMAIL_VERIFICATION": "False",
    "FRONTEND_EMAIL_VERIFICATION_URL": "",
    "EMAIL_VERIFICATION_TIMEOUT_HOURS": "24",
    "ALLOW_PUBLIC_REGISTRATION": "True",
    "API_KEYS_ENABLED": "False",
    "TOTP_ENABLED": "False",
    "TOTP_ENCRYPTION_KEY": "",
    "TOTP_ISSUER": "",
    "GOOGLE_CLIENT_IDS": "",
    "WEBHOOKS_ENABLED": "False",
    "WEBHOOK_MAX_ATTEMPTS": "5",
    "WEBHOOK_TIMEOUT_SECONDS": "10",
    "WEBHOOK_ALLOW_PRIVATE_URLS": "",
    "GOOGLE_JWKS_URL": "https://www.googleapis.com/oauth2/v3/certs",
    "CORS_ALLOWED_ORIGINS": "",
    "API_PAGE_SIZE": "20",
    "API_MAX_PAGE_SIZE": "100",
    "API_DOCS_ENABLED": "",
    "DB_NAME": "unused",
    "DB_USER": "unused",
    "DB_PASSWORD": "not-the-example-password",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_CONN_MAX_AGE": "60",
    "LOG_LEVEL": "INFO",
    "LOG_FORMAT": "text",
    "ADMIN_PASSWORD": "not-the-example-password",
}

READ_SETTINGS_SCRIPT = """
import json, sys
import django
django.setup()
from django.conf import settings
print(json.dumps({name: getattr(settings, name) for name in sys.argv[1:]}, default=str))
"""


def build_environment(overrides):
    return {
        "PATH": os.environ["PATH"],
        "DJANGO_SETTINGS_MODULE": "core.settings",
        **PRODUCTION_ENVIRONMENT,
        **overrides,
    }


def run_python(arguments, overrides):
    return subprocess.run(  # noqa: S603 - the interpreter and arguments come from the tests
        [sys.executable, *arguments],
        cwd=PROJECT_ROOT,
        env=build_environment(overrides),
        capture_output=True,
        text=True,
        timeout=60,
    )


def run_manage_command(arguments, **overrides):
    return run_python(["manage.py", *arguments], overrides)


def read_settings(names, **overrides):
    result = run_python(["-c", READ_SETTINGS_SCRIPT, *names], overrides)
    if result.returncode != 0:
        raise AssertionError(f"Settings failed to load:\n{result.stderr}")
    return json.loads(result.stdout)

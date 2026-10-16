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
    "CACHE_URL": "locmemcache://",
    "THROTTLE_ANON_RATE": "",
    "THROTTLE_USER_RATE": "",
    "THROTTLE_LOGIN_RATE": "10/10m",
    "THROTTLE_REGISTER_RATE": "5/h",
    "THROTTLE_PASSWORD_RATE": "5/h",
    "JWT_ACCESS_MINUTES": "5",
    "JWT_REFRESH_DAYS": "1",
    "JWT_SIGNING_KEY": "",
    "AXES_FAILURE_LIMIT": "5",
    "AXES_COOLOFF_MINUTES": "15",
    "AXES_LOCKOUT_PARAMETERS": "username+ip_address",
    "DB_NAME": "unused",
    "DB_USER": "unused",
    "DB_PASSWORD": "not-the-example-password",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
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

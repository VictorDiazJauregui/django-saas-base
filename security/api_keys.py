import hashlib
import hmac
import secrets

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiKey

PREFIX_BYTES = 6
SECRET_BYTES = 32
SEPARATOR = "."
INVALID_API_KEY_CODE = "invalid_api_key"
INVALID_API_KEY_MESSAGE = _("Invalid API key.")


# The secret is 32 random bytes: a fast hash is enough, a slow one would only add latency to
# every request authenticated with a key.
def hash_api_key(raw_key):
    return hashlib.sha256(raw_key.encode()).hexdigest()


def assign_new_key(api_key):
    api_key.prefix = secrets.token_hex(PREFIX_BYTES)
    raw_key = f"{api_key.prefix}{SEPARATOR}{secrets.token_urlsafe(SECRET_BYTES)}"
    api_key.key_hash = hash_api_key(raw_key)
    return raw_key


def issue_api_key(user, name, expires_at=None):
    api_key = ApiKey(user=user, name=name, expires_at=expires_at)
    raw_key = assign_new_key(api_key)
    api_key.save()
    return api_key, raw_key


def find_usable_api_key(raw_key):
    prefix = raw_key.partition(SEPARATOR)[0]
    api_key = ApiKey.objects.select_related("user").filter(prefix=prefix).first()
    if api_key is None:
        return None
    if not hmac.compare_digest(api_key.key_hash, hash_api_key(raw_key)):
        return None
    return api_key if api_key.is_usable() else None


def authenticate_api_key(raw_key):
    api_key = find_usable_api_key(raw_key)
    if api_key is None:
        raise AuthenticationFailed(INVALID_API_KEY_MESSAGE, INVALID_API_KEY_CODE)
    api_key.last_used_at = timezone.now()
    ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=api_key.last_used_at)
    return api_key


def revoke_api_keys(api_keys):
    return api_keys.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())

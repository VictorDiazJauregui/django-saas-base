from datetime import timedelta

from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

from security.api_keys import (
    INVALID_API_KEY_CODE,
    INVALID_API_KEY_MESSAGE,
    assign_new_key,
    matches_key_hash,
    read_key_prefix,
)

from .models import Organization, OrganizationApiKey

ORGANIZATION_API_KEY_MARKER = "org_"
# Writing the last use on every request would turn each read into a write.
LAST_USE_REFRESH_INTERVAL = timedelta(minutes=5)


def is_organization_api_key(raw_key: str) -> bool:
    return raw_key.startswith(ORGANIZATION_API_KEY_MARKER)


def issue_organization_api_key(
    organization: Organization, details: dict
) -> tuple[OrganizationApiKey, str]:
    api_key = OrganizationApiKey(organization=organization, **details)
    raw_key = assign_new_key(api_key, ORGANIZATION_API_KEY_MARKER)
    api_key.save()
    return api_key, raw_key


def find_usable_organization_api_key(raw_key: str) -> OrganizationApiKey | None:
    api_keys = OrganizationApiKey.objects.select_related("organization")
    api_key = api_keys.filter(prefix=read_key_prefix(raw_key)).first()
    if api_key is None or not matches_key_hash(api_key.key_hash, raw_key):
        return None
    return api_key if api_key.is_usable() else None


def authenticate_organization_api_key(raw_key: str) -> OrganizationApiKey:
    api_key = find_usable_organization_api_key(raw_key)
    if api_key is None:
        raise AuthenticationFailed(INVALID_API_KEY_MESSAGE, INVALID_API_KEY_CODE)
    record_organization_api_key_use(api_key)
    return api_key


def record_organization_api_key_use(api_key: OrganizationApiKey) -> None:
    now = timezone.now()
    stale = Q(last_used_at__isnull=True) | Q(
        last_used_at__lt=now - LAST_USE_REFRESH_INTERVAL
    )
    OrganizationApiKey.objects.filter(stale, pk=api_key.pk).update(last_used_at=now)


def revoke_organization_api_keys(api_keys: QuerySet[OrganizationApiKey]) -> int:
    return api_keys.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())

from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)


def revoke_refresh_tokens(user):
    pending_tokens = OutstandingToken.objects.filter(
        user=user, expires_at__gt=timezone.now(), blacklistedtoken__isnull=True
    )
    revocations = [BlacklistedToken(token=token) for token in pending_tokens]
    BlacklistedToken.objects.bulk_create(revocations, ignore_conflicts=True)
    return len(revocations)

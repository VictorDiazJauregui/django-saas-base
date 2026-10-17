from axes.signals import user_locked_out
from django.contrib.auth.signals import user_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User
from .security_events import log_failed_login, log_lockout, log_tokens_revoked
from .token_revocation import revoke_refresh_tokens


@receiver(post_save, sender=User)
def revoke_tokens_after_password_change(sender, instance, created, **kwargs):
    if created or not instance.has_password_hash_changed():
        return
    revoked = revoke_refresh_tokens(instance)
    log_tokens_revoked(instance, revoked, "password_changed")
    instance.remember_password_hash()


# Django sends it for the API and the admin alike, with the password already masked.
@receiver(user_login_failed)
def log_failed_login_attempt(sender, credentials, request=None, **kwargs):
    log_failed_login(request, credentials)


# axes sends it when an account gets locked and on every attempt while it stays locked.
@receiver(user_locked_out)
def log_locked_out_attempt(sender, request, username, ip_address, **kwargs):
    log_lockout(username, ip_address)

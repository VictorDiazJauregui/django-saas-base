from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User
from .token_revocation import revoke_refresh_tokens


@receiver(post_save, sender=User)
def revoke_tokens_after_password_change(sender, instance, created, **kwargs):
    if created or not instance.has_password_hash_changed():
        return
    revoke_refresh_tokens(instance)
    instance.remember_password_hash()

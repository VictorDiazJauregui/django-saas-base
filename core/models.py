from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        abstract = True


# delete() answers like Django's, (count, {label: count}), so code written for a hard delete
# keeps working when a model switches to the soft one.
class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        count = self.update(deleted_at=timezone.now())
        return count, {self.model._meta.label: count}

    def hard_delete(self):
        return super().delete()

    def restore(self):
        return self.update(deleted_at=None)

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)


class AliveManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    def get_queryset(self):
        return super().get_queryset().alive()


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    objects = AliveManager()
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=["deleted_at"])
        return 1, {self._meta.label: 1}

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

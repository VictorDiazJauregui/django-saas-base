from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import TimestampedModel


class WebhookEndpoint(TimestampedModel):
    url = models.URLField(_("URL"), max_length=500)
    description = models.CharField(_("description"), max_length=200, blank=True)
    events = ArrayField(
        models.CharField(max_length=100),
        verbose_name=_("events"),
        help_text=_("Event names separated by commas, such as user.registered."),
    )
    # Kept readable: every delivery is signed with it.
    secret = models.CharField(_("secret"), max_length=64, editable=False)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("webhook endpoint")
        verbose_name_plural = _("webhook endpoints")
        ordering = ["-created_at"]

    def __str__(self):
        return self.url


class WebhookDelivery(TimestampedModel):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STATUSES = [
        (PENDING, _("Pending")),
        (SUCCEEDED, _("Succeeded")),
        (FAILED, _("Failed")),
    ]

    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name="deliveries",
        verbose_name=_("endpoint"),
    )
    event = models.CharField(_("event"), max_length=100)
    payload = models.JSONField(_("payload"))
    status = models.CharField(
        _("status"), max_length=10, choices=STATUSES, default=PENDING
    )
    attempts = models.PositiveSmallIntegerField(_("attempts"), default=0)
    next_attempt_at = models.DateTimeField(_("next attempt at"), default=timezone.now)
    last_status_code = models.PositiveSmallIntegerField(
        _("last status code"), null=True, blank=True
    )
    last_error = models.CharField(_("last error"), max_length=255, blank=True)
    delivered_at = models.DateTimeField(_("delivered at"), null=True, blank=True)

    class Meta:
        verbose_name = _("webhook delivery")
        verbose_name_plural = _("webhook deliveries")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at"], name="webhook_delivery_due_idx"
            )
        ]

    def __str__(self):
        return f"{self.event} → {self.endpoint}"

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimestampedModel

from .roles import OrganizationRole
from .slugs import SLUG_MAX_LENGTH, build_unique_slug


class Organization(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=100)
    slug = models.SlugField(
        _("slug"), max_length=SLUG_MAX_LENGTH, unique=True, blank=True
    )

    class Meta:
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = build_unique_slug(self.name)
        super().save(*args, **kwargs)


class Membership(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("User"),
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("organization"),
    )
    role = models.CharField(
        _("role"),
        max_length=10,
        choices=OrganizationRole.choices,
        default=OrganizationRole.MEMBER,
    )

    class Meta:
        verbose_name = _("membership")
        verbose_name_plural = _("memberships")
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="unique_membership_per_organization",
            )
        ]

    def __str__(self):
        return f"{self.user} · {self.get_role_display()} · {self.organization}"


class OrganizationScopedModel(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, verbose_name=_("organization")
    )

    class Meta:
        abstract = True

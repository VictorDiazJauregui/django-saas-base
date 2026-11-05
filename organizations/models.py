import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
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


# Only the hash of the token is stored, as with API keys: the table or a backup can't be
# used to join an organization.
class Invitation(TimestampedModel):
    PENDING, ACCEPTED, REVOKED, EXPIRED = "pending", "accepted", "revoked", "expired"
    STATUS_LABELS = {
        PENDING: _("Pending"),
        ACCEPTED: _("Accepted"),
        REVOKED: _("Revoked"),
        EXPIRED: _("Expired"),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invitations",
        verbose_name=_("organization"),
    )
    email = models.EmailField(_("email address"))
    role = models.CharField(_("role"), max_length=10, choices=OrganizationRole.choices)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("invited by"),
    )
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    expires_at = models.DateTimeField(_("expires at"))
    accepted_at = models.DateTimeField(_("accepted at"), null=True, blank=True)
    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)

    class Meta:
        verbose_name = _("invitation")
        verbose_name_plural = _("invitations")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                "organization",
                condition=Q(accepted_at__isnull=True, revoked_at__isnull=True),
                name="unique_open_invitation_per_email",
            )
        ]

    def __str__(self):
        return f"{self.email} → {self.organization}"

    @property
    def status(self):
        if self.accepted_at is not None:
            return self.ACCEPTED
        if self.revoked_at is not None:
            return self.REVOKED
        if self.expires_at <= timezone.now():
            return self.EXPIRED
        return self.PENDING


class OrganizationScopedModel(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, verbose_name=_("organization")
    )

    class Meta:
        abstract = True

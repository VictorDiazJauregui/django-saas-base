import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    @classmethod
    def normalize_email(cls, email):
        return (email or "").strip().lower()

    def get_by_natural_key(self, email):
        return self.get(email__iexact=email)

    def is_email_taken(self, email):
        return self.filter(email__iexact=email).exists()

    def create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError(_("The Email must be set"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    # A random UUID keeps the user count and other users' ids out of tokens and URLs.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(_("email address"), unique=True)
    # Only the public registration creates unverified accounts. is_active stays for the admin
    # to disable an account, so a pending verification can never re-enable a disabled one.
    is_email_verified = models.BooleanField(_("email verified"), default=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("email"), name="unique_user_email_ignoring_case"
            )
        ]

    # clean() lowercases the email, so the unique check of the field already reports a duplicate
    # in any case. Validating this constraint too would show the same error twice in forms; the
    # database still enforces it.
    def validate_constraints(self, exclude=None):
        super().validate_constraints(exclude={*(exclude or ()), "email"})

    def save(self, *args, **kwargs):
        self.email = type(self).objects.normalize_email(self.email)
        super().save(*args, **kwargs)

    # Every way of changing a password ends in save(), so comparing the hash read from the
    # database with the one being saved catches all of them without an extra query.
    @classmethod
    def from_db(cls, db, field_names, values):
        user = super().from_db(db, field_names, values)
        user.remember_password_hash()
        return user

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        self.remember_password_hash()

    def remember_password_hash(self):
        self._loaded_password_hash = self.__dict__.get("password")

    def has_password_hash_changed(self):
        loaded_hash = getattr(self, "_loaded_password_hash", None)
        return loaded_hash is not None and self.__dict__.get("password") != loaded_hash

    def __str__(self):
        return self.email


class AuditLog(models.Model):
    """
    Model to store audit logs for modification requests.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("User"),
    )
    ip_address = models.GenericIPAddressField(_("IP Address"), null=True, blank=True)
    user_agent = models.CharField(_("User Agent"), max_length=255, blank=True)
    method = models.CharField(_("HTTP Method"), max_length=10)
    path = models.CharField(_("URL Path"), max_length=255)
    payload = models.JSONField(_("Payload"), null=True, blank=True)
    status_code = models.PositiveSmallIntegerField(
        _("Status code"), null=True, blank=True
    )
    timestamp = models.DateTimeField(_("Timestamp"), auto_now_add=True)

    class Meta:
        verbose_name = _("Audit Log")
        verbose_name_plural = _("Audit Logs")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["timestamp"], name="auditlog_timestamp_idx"),
            models.Index(
                fields=["user", "timestamp"], name="auditlog_user_timestamp_idx"
            ),
        ]

    def __str__(self):
        return f"{self.method} {self.path} by {self.user or 'Anonymous'} at {self.timestamp}"

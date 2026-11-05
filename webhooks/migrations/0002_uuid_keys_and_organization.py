import uuid

import django.contrib.postgres.fields
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0004_organization_api_key"),
        ("webhooks", "0001_initial"),
    ]

    # PostgreSQL can't cast a bigint key to uuid: both tables are recreated empty, as the
    # release notes announce.
    operations = [
        migrations.DeleteModel(name="WebhookDelivery"),
        migrations.DeleteModel(name="WebhookEndpoint"),
        migrations.CreateModel(
            name="WebhookEndpoint",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                ("url", models.URLField(max_length=500, verbose_name="URL")),
                (
                    "description",
                    models.CharField(
                        blank=True, max_length=200, verbose_name="description"
                    ),
                ),
                (
                    "events",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=100),
                        help_text="Event names separated by commas, such as user.registered.",
                        size=None,
                        verbose_name="events",
                    ),
                ),
                (
                    "secret",
                    models.CharField(
                        editable=False, max_length=64, verbose_name="secret"
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="webhook_endpoints",
                        to="organizations.organization",
                        verbose_name="organization",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="active")),
            ],
            options={
                "verbose_name": "webhook endpoint",
                "verbose_name_plural": "webhook endpoints",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="WebhookDelivery",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                ("event", models.CharField(max_length=100, verbose_name="event")),
                ("payload", models.JSONField(verbose_name="payload")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=10,
                        verbose_name="status",
                    ),
                ),
                (
                    "attempts",
                    models.PositiveSmallIntegerField(
                        default=0, verbose_name="attempts"
                    ),
                ),
                (
                    "next_attempt_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        verbose_name="next attempt at",
                    ),
                ),
                (
                    "last_status_code",
                    models.PositiveSmallIntegerField(
                        blank=True, null=True, verbose_name="last status code"
                    ),
                ),
                (
                    "last_error",
                    models.CharField(
                        blank=True, max_length=255, verbose_name="last error"
                    ),
                ),
                (
                    "delivered_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="delivered at"
                    ),
                ),
                (
                    "endpoint",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deliveries",
                        to="webhooks.webhookendpoint",
                        verbose_name="endpoint",
                    ),
                ),
            ],
            options={
                "verbose_name": "webhook delivery",
                "verbose_name_plural": "webhook deliveries",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["status", "next_attempt_at"],
                        name="webhook_delivery_due_idx",
                    )
                ],
            },
        ),
    ]

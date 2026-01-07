import json

from django.contrib import admin
from django.utils.html import format_html

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin para AuditLog: vista en tabla con búsqueda y detalle con payload formateado."""

    list_display = (
        "timestamp",
        "user",
        "method",
        "path",
        "ip_address",
        "short_payload",
    )
    list_filter = ("method", "user", "timestamp")
    search_fields = (
        "user__email",
        "path",
        "method",
        "ip_address",
        "user_agent",
        "payload",
    )
    readonly_fields = (
        "user",
        "ip_address",
        "user_agent",
        "method",
        "path",
        "pretty_payload",
        "timestamp",
    )
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)
    list_per_page = 25

    fields = (
        "timestamp",
        "user",
        "ip_address",
        "user_agent",
        "method",
        "path",
        "pretty_payload",
    )

    def short_payload(self, obj):
        """Muestra una versión truncada del payload en la vista de lista."""
        if not obj.payload:
            return "-"
        s = json.dumps(obj.payload, ensure_ascii=False)
        return s if len(s) <= 75 else s[:72] + "..."

    short_payload.short_description = "Payload"

    def pretty_payload(self, obj):
        """Muestra el payload como JSON formateado en la vista detalle."""
        if not obj.payload:
            return "-"
        try:
            pretty = json.dumps(obj.payload, indent=2, ensure_ascii=False)
        except Exception:
            pretty = str(obj.payload)
        return format_html("<pre style='white-space: pre-wrap;'>{}</pre>", pretty)

    pretty_payload.short_description = "Payload (formateado)"

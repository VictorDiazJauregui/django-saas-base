from core.client_ip import get_client_ip

from .audit_payload import BODY_METHODS, read_audit_payload
from .models import AuditLog
from .redaction import redact_sensitive_values

AUDITED_METHODS = BODY_METHODS | {"DELETE"}


def truncate_to_column_length(field_name, value):
    max_length = AuditLog._meta.get_field(field_name).max_length
    return value[:max_length]


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # The body is read before the view runs: once the view consumes the stream
        # it can no longer be read.
        payload = read_audit_payload(request)
        response = self.get_response(request)
        if request.method in AUDITED_METHODS:
            self.record_request(request, response, payload)
        return response

    def record_request(self, request, response, payload):
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        AuditLog.objects.create(
            user=self.resolve_user(request),
            ip_address=get_client_ip(request),
            user_agent=truncate_to_column_length("user_agent", user_agent),
            method=request.method,
            path=truncate_to_column_length("path", request.path),
            payload=redact_sensitive_values(payload),
            status_code=response.status_code,
        )

    def resolve_user(self, request):
        user_for_audit = getattr(request, "user_for_audit", None)
        if user_for_audit is not None:
            return user_for_audit
        if request.user.is_authenticated:
            return request.user
        return None

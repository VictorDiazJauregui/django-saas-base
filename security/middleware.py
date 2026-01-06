import json
from .models import AuditLog

class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # For POST/PUT/PATCH, we read the body before it's consumed by the view.
        # This allows us to log it later without causing a RawPostDataException.
        body_for_log = {}
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if request.content_type == 'application/json':
                    body_for_log = json.loads(request.body)
                    # We keep a copy of the raw body in case the stream is consumed.
                    # This allows the view to re-read it if necessary.
                    request._body = request.body
            except (json.JSONDecodeError, AttributeError):
                pass  # Ignore if body is not valid JSON or not present

        response = self.get_response(request)
        
        # After the view has been processed, we log the request.
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            # Check if the view attached a user for us (for login events)
            user = getattr(request, 'user_for_audit', None)
            # If not, use the standard authenticated user
            if user is None and request.user.is_authenticated:
                user = request.user

            # Redact sensitive data from the cached body
            payload = self.redact_sensitive_data(body_for_log)

            AuditLog.objects.create(
                user=user,
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                method=request.method,
                path=request.path,
                payload=payload
            )
            
        return response

    def get_client_ip(self, request):
        """Get client IP address from the request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def redact_sensitive_data(self, payload):
        """Recursively redact sensitive keys from a dictionary."""
        if not isinstance(payload, dict):
            return payload
            
        sensitive_keys = ['password', 'token', 'secret', 'access', 'refresh']
        clean_payload = payload.copy()

        for key, value in clean_payload.items():
            if key in sensitive_keys:
                clean_payload[key] = '[REDACTED]'
            elif isinstance(value, dict):
                clean_payload[key] = self.redact_sensitive_data(value)
        
        return clean_payload

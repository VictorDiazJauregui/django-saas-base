from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse
from rest_framework import serializers


class ApiErrorSerializer(serializers.Serializer):
    code = serializers.CharField(
        help_text=_("Fixed identifier for the frontend to branch on.")
    )
    detail = serializers.CharField(
        help_text=_("Message for a person, in the request's language.")
    )
    fields = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()),
        help_text=_("Messages per field, only in validation errors; {} otherwise."),
    )


class DetailMessageSerializer(serializers.Serializer):
    detail = serializers.CharField()


# code -> (status, detail, fields) of the example each documented error shows.
ERROR_EXAMPLES = {
    "invalid": (400, "Invalid input.", {"email": ["Enter a valid email address."]}),
    "not_authenticated": (401, "Authentication credentials were not provided.", {}),
    "token_not_valid": (401, "Token is invalid or expired", {}),
    "no_active_account": (
        401,
        "No active account found with the given credentials",
        {},
    ),
    "permission_denied": (403, "Public registration is disabled.", {}),
    "throttled": (429, "Request was throttled. Expected available in 60 seconds.", {}),
    "account_locked_out": (429, "Too many failed login attempts.", {}),
}

RETRY_AFTER_HEADER = OpenApiParameter(
    name="Retry-After",
    type=OpenApiTypes.INT,
    location=OpenApiParameter.HEADER,
    response=[429],
    description=_("Seconds to wait before trying again."),
)


def build_error_example(code):
    status, detail, fields = ERROR_EXAMPLES[code]
    value = {"code": code, "detail": detail, "fields": fields}
    return status, OpenApiExample(code, value=value, response_only=True)


def error_responses(*codes):
    examples_by_status = {}
    for code in codes:
        status, example = build_error_example(code)
        examples_by_status.setdefault(status, []).append(example)
    return {
        status: OpenApiResponse(ApiErrorSerializer, examples=examples)
        for status, examples in examples_by_status.items()
    }

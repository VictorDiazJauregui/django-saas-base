from django.http import JsonResponse
from django.views import defaults
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.settings import api_settings
from rest_framework.views import exception_handler

API_PATH_PREFIX = "/api/"
SERVER_ERROR_CODE = "server_error"
FALLBACK_CODE = "error"


def build_error_body(code, detail, fields=None):
    return {"code": str(code), "detail": str(detail), "fields": fields or {}}


def as_field_errors(errors):
    if isinstance(errors, dict):
        return errors
    return {api_settings.NON_FIELD_ERRORS_KEY: errors}


def describe_detail_error(error):
    detail = error["detail"]
    code = error.get("code") or getattr(detail, "code", FALLBACK_CODE)
    return build_error_body(code, detail)


# DRF hands over the error already turned into data: {"detail": ...} for most errors,
# a dict or list of messages for validation, and SimpleJWT adds "code" and "messages".
def describe_error(exc, error):
    if isinstance(exc, ValidationError):
        return build_error_body(
            ValidationError.default_code,
            ValidationError.default_detail,
            as_field_errors(error),
        )
    if isinstance(error, dict) and "detail" in error:
        return describe_detail_error(error)
    return build_error_body(
        APIException.default_code, APIException.default_detail, as_field_errors(error)
    )


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    response.data = describe_error(exc, response.data)
    return response


def is_api_request(request):
    return request.path.startswith(API_PATH_PREFIX)


def api_not_found(request, exception):
    if not is_api_request(request):
        return defaults.page_not_found(request, exception)
    body = build_error_body(NotFound.default_code, NotFound.default_detail)
    return JsonResponse(body, status=status.HTTP_404_NOT_FOUND)


def api_server_error(request):
    if not is_api_request(request):
        return defaults.server_error(request)
    body = build_error_body(SERVER_ERROR_CODE, APIException.default_detail)
    return JsonResponse(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

import json

from django.conf import settings
from django.http import QueryDict

BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})
CSRF_FIELD = "csrfmiddlewaretoken"


def read_audit_payload(request):
    if request.method not in BODY_METHODS:
        return {}
    read_payload = PAYLOAD_READERS.get(request.content_type)
    if read_payload is None:
        return {}
    return read_payload(request)


# The size is measured on the raw body before parsing it: an oversized body is never parsed, and
# a truncated JSON would be invalid and could cut a sensitive key before it is redacted.
def read_json_payload(request):
    body = request.body
    if exceeds_payload_limit(len(body)):
        return build_omitted_payload(len(body))
    try:
        return json.loads(body)
    except ValueError:
        return {}


# Parsed from the body rather than request.POST, which Django only fills on POST.
def read_urlencoded_payload(request):
    body = request.body
    if exceeds_payload_limit(len(body)):
        return build_omitted_payload(len(body))
    return flatten_form_fields(QueryDict(body, encoding=request.encoding))


# request.body would load every uploaded file into memory and fails above
# DATA_UPLOAD_MAX_MEMORY_SIZE, so only the fields Django already parsed are read and measured.
def read_multipart_payload(request):
    if request.method != "POST":
        return {}
    fields = flatten_form_fields(request.POST)
    fields_size = len(json.dumps(fields, ensure_ascii=False).encode())
    if exceeds_payload_limit(fields_size):
        return build_omitted_payload(fields_size)
    return fields


def flatten_form_fields(form_fields):
    return {
        name: values[0] if len(values) == 1 else values
        for name, values in form_fields.lists()
        if name != CSRF_FIELD
    }


def exceeds_payload_limit(size_bytes):
    limit = settings.AUDIT_PAYLOAD_MAX_BYTES
    return limit > 0 and size_bytes > limit


def build_omitted_payload(size_bytes):
    return {"_omitted": "payload_too_large", "size_bytes": size_bytes}


PAYLOAD_READERS = {
    "application/json": read_json_payload,
    "application/x-www-form-urlencoded": read_urlencoded_payload,
    "multipart/form-data": read_multipart_payload,
}

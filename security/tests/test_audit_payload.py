import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings

from security.audit_payload import read_audit_payload

PAYLOAD_LIMIT = 64
URLENCODED = "application/x-www-form-urlencoded"


def json_body_of_size(size):
    base = {"email": "a@b.co", "note": ""}
    filler = size - len(json.dumps(base).encode())
    return json.dumps({**base, "note": "x" * filler}).encode()


@override_settings(AUDIT_PAYLOAD_MAX_BYTES=PAYLOAD_LIMIT)
class JsonPayloadSizeTests(SimpleTestCase):
    def read_json(self, body):
        request = RequestFactory().post("/", body, content_type="application/json")
        return read_audit_payload(request)

    def test_keeps_a_body_exactly_at_the_limit(self):
        body = json_body_of_size(PAYLOAD_LIMIT)

        self.assertEqual(self.read_json(body), json.loads(body))

    def test_stores_a_marker_one_byte_over_the_limit(self):
        body = json_body_of_size(PAYLOAD_LIMIT + 1)

        self.assertEqual(
            self.read_json(body),
            {"_omitted": "payload_too_large", "size_bytes": PAYLOAD_LIMIT + 1},
        )

    def test_stores_a_marker_for_oversized_malformed_json(self):
        body = b"{" * (PAYLOAD_LIMIT + 10)

        self.assertEqual(self.read_json(body)["size_bytes"], PAYLOAD_LIMIT + 10)

    @override_settings(AUDIT_PAYLOAD_MAX_BYTES=0)
    def test_zero_keeps_every_body(self):
        body = json_body_of_size(PAYLOAD_LIMIT * 10)

        self.assertEqual(self.read_json(body), json.loads(body))


class FormPayloadTests(SimpleTestCase):
    def test_reads_urlencoded_fields_as_single_values(self):
        request = RequestFactory().post(
            "/", "email=a%40b.co&first_name=Ana", content_type=URLENCODED
        )

        self.assertEqual(
            read_audit_payload(request), {"email": "a@b.co", "first_name": "Ana"}
        )

    def test_keeps_every_value_of_a_repeated_key(self):
        request = RequestFactory().post("/", "a=1&a=2", content_type=URLENCODED)

        self.assertEqual(read_audit_payload(request), {"a": ["1", "2"]})

    def test_drops_the_csrf_token(self):
        request = RequestFactory().post(
            "/", "csrfmiddlewaretoken=abc&email=a%40b.co", content_type=URLENCODED
        )

        self.assertEqual(read_audit_payload(request), {"email": "a@b.co"})

    def test_reads_urlencoded_fields_on_patch(self):
        request = RequestFactory().patch("/", "note=hi", content_type=URLENCODED)

        self.assertEqual(read_audit_payload(request), {"note": "hi"})

    def test_reads_multipart_fields_without_the_files(self):
        upload = SimpleUploadedFile("avatar.png", b"\x89PNG" * 100)
        request = RequestFactory().post("/", {"email": "a@b.co", "avatar": upload})

        self.assertEqual(read_audit_payload(request), {"email": "a@b.co"})

    @override_settings(AUDIT_PAYLOAD_MAX_BYTES=PAYLOAD_LIMIT)
    def test_measures_multipart_fields_without_the_files(self):
        upload = SimpleUploadedFile("big.bin", b"0" * (PAYLOAD_LIMIT * 100))
        request = RequestFactory().post("/", {"email": "a@b.co", "avatar": upload})

        self.assertEqual(read_audit_payload(request), {"email": "a@b.co"})

    @override_settings(AUDIT_PAYLOAD_MAX_BYTES=PAYLOAD_LIMIT)
    def test_stores_a_marker_for_oversized_multipart_fields(self):
        fields = {"note": "x" * PAYLOAD_LIMIT}
        request = RequestFactory().post("/", fields)

        marker = read_audit_payload(request)

        self.assertEqual(marker["_omitted"], "payload_too_large")
        self.assertEqual(marker["size_bytes"], len(json.dumps(fields).encode()))

    @override_settings(AUDIT_PAYLOAD_MAX_BYTES=PAYLOAD_LIMIT)
    def test_stores_a_marker_for_oversized_urlencoded_body(self):
        body = "note=" + "x" * PAYLOAD_LIMIT
        request = RequestFactory().post("/", body, content_type=URLENCODED)

        self.assertEqual(read_audit_payload(request)["size_bytes"], len(body))


class IgnoredPayloadTests(SimpleTestCase):
    def test_ignores_unknown_content_types(self):
        request = RequestFactory().post("/", "<a/>", content_type="application/xml")

        self.assertEqual(read_audit_payload(request), {})

    def test_ignores_bodies_of_delete_requests(self):
        request = RequestFactory().delete(
            "/", '{"a": 1}', content_type="application/json"
        )

        self.assertEqual(read_audit_payload(request), {})

    def test_ignores_multipart_outside_post(self):
        request = RequestFactory().put(
            "/", "--x--\r\n", content_type="multipart/form-data; boundary=x"
        )

        self.assertEqual(read_audit_payload(request), {})

import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase
from drf_spectacular.generators import SchemaGenerator

AUTH = "/api/v1/auth"
EXPECTED_OPERATIONS = {
    ("post", f"{AUTH}/register/"),
    ("post", f"{AUTH}/login/"),
    ("post", f"{AUTH}/login/refresh/"),
    ("post", f"{AUTH}/logout/"),
    ("get", f"{AUTH}/me/"),
    ("patch", f"{AUTH}/me/"),
    ("post", f"{AUTH}/password/change/"),
    ("post", f"{AUTH}/password/reset/"),
    ("post", f"{AUTH}/password/reset/confirm/"),
    ("post", f"{AUTH}/verify-email/"),
    ("post", f"{AUTH}/verify-email/resend/"),
}
NO_CONTENT_OPERATIONS = (
    f"{AUTH}/password/change/",
    f"{AUTH}/password/reset/confirm/",
    f"{AUTH}/verify-email/",
)
ERROR_REFERENCE = "#/components/schemas/ApiError"


def response_schema(operation, status_code):
    return operation["responses"][status_code]["content"]["application/json"]["schema"]


class OpenApiSchemaTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = SchemaGenerator().get_schema(request=None, public=True)
        cls.paths = cls.schema["paths"]
        cls.components = cls.schema["components"]

    def operation(self, method, path):
        return self.paths[path][method]

    def test_validates_without_warnings(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "openapi.yml"
            call_command(
                "spectacular", "--validate", "--fail-on-warn", "--file", str(output)
            )

            self.assertTrue(output.read_text().startswith("openapi: 3.0.3"))

    def test_describes_the_api_under_a_neutral_title(self):
        self.assertEqual(self.schema["info"]["title"], "API")
        self.assertEqual(self.schema["info"]["version"], "v1")

    def test_lists_every_auth_and_account_operation(self):
        operations = {
            (method, path) for path, item in self.paths.items() for method in item
        }

        self.assertEqual(operations, EXPECTED_OPERATIONS)

    def test_bearer_scheme_protects_the_profile(self):
        scheme = self.components["securitySchemes"]["jwtAuth"]

        self.assertEqual((scheme["type"], scheme["scheme"]), ("http", "bearer"))
        self.assertIn({"jwtAuth": []}, self.operation("get", f"{AUTH}/me/")["security"])

    def test_public_routes_ask_for_no_token(self):
        for path in (f"{AUTH}/password/reset/", f"{AUTH}/verify-email/"):
            with self.subTest(path=path):
                security = self.operation("post", path).get("security", [{}])

                self.assertNotIn({"jwtAuth": []}, security)

    def test_error_shape_is_a_component(self):
        error = self.components["schemas"]["ApiError"]

        self.assertEqual(set(error["properties"]), {"code", "detail", "fields"})
        self.assertEqual(set(error["required"]), {"code", "detail", "fields"})

    def test_errors_point_to_the_error_shape(self):
        cases = (
            ("post", f"{AUTH}/register/", "400"),
            ("post", f"{AUTH}/login/", "401"),
            ("post", f"{AUTH}/login/", "429"),
            ("get", f"{AUTH}/me/", "401"),
            ("post", f"{AUTH}/password/change/", "400"),
        )
        for method, path, status_code in cases:
            with self.subTest(path=path, status=status_code):
                schema = response_schema(self.operation(method, path), status_code)

                self.assertEqual(schema["$ref"], ERROR_REFERENCE)

    def test_rate_limited_answers_document_retry_after(self):
        throttled = self.operation("post", f"{AUTH}/login/")["responses"]["429"]

        self.assertIn("Retry-After", throttled["headers"])

    def test_no_content_answers_have_no_body(self):
        for path in NO_CONTENT_OPERATIONS:
            with self.subTest(path=path):
                responses = self.operation("post", path)["responses"]

                self.assertNotIn("content", responses["204"])
                self.assertNotIn("200", responses)

    def test_message_answers_return_detail(self):
        for path in (f"{AUTH}/password/reset/", f"{AUTH}/verify-email/resend/"):
            with self.subTest(path=path):
                schema = response_schema(self.operation("post", path), "200")

                self.assertEqual(schema["$ref"], "#/components/schemas/DetailMessage")

    def test_passwords_only_appear_in_request_types(self):
        schema = response_schema(self.operation("post", f"{AUTH}/register/"), "201")
        response_type = schema["$ref"].rsplit("/", 1)[-1]
        request_type = f"{response_type}Request"

        self.assertNotIn(
            "password", self.components["schemas"][response_type]["properties"]
        )
        self.assertIn(
            "password", self.components["schemas"][request_type]["properties"]
        )

    def test_descriptions_are_written_for_the_client_not_taken_from_docstrings(self):
        for path, item in self.paths.items():
            for method, operation in item.items():
                with self.subTest(method=method, path=path):
                    self.assertNotIn(
                        "AuditMiddleware", operation.get("description", "")
                    )

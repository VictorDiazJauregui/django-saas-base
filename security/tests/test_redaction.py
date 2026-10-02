from django.test import SimpleTestCase

from security.redaction import REDACTED_PLACEHOLDER, redact_sensitive_values


class RedactSensitiveValuesTests(SimpleTestCase):
    def test_redacts_keys_containing_a_sensitive_fragment(self):
        payload = {"password2": "a", "api_token": "b", "client_secret": "c"}

        redacted = redact_sensitive_values(payload)

        self.assertEqual(set(redacted.values()), {REDACTED_PLACEHOLDER})

    def test_redacts_keys_regardless_of_letter_case(self):
        redacted = redact_sensitive_values({"NewPassword": "a"})

        self.assertEqual(redacted["NewPassword"], REDACTED_PLACEHOLDER)

    def test_redacts_token_pair_keys(self):
        redacted = redact_sensitive_values({"access": "a", "refresh": "b"})

        self.assertEqual(set(redacted.values()), {REDACTED_PLACEHOLDER})

    def test_keeps_non_sensitive_values(self):
        payload = {"email": "jane.doe@example.com", "accessibility": "high"}

        self.assertEqual(redact_sensitive_values(payload), payload)

    def test_redacts_nested_dictionaries(self):
        redacted = redact_sensitive_values({"profile": {"password": "a", "age": 30}})

        self.assertEqual(
            redacted, {"profile": {"password": REDACTED_PLACEHOLDER, "age": 30}}
        )

    def test_redacts_dictionaries_inside_lists(self):
        redacted = redact_sensitive_values({"users": [{"password": "a"}]})

        self.assertEqual(redacted, {"users": [{"password": REDACTED_PLACEHOLDER}]})

    def test_does_not_mutate_the_original_payload(self):
        payload = {"password": "a"}

        redact_sensitive_values(payload)

        self.assertEqual(payload, {"password": "a"})

    def test_returns_scalar_payloads_unchanged(self):
        self.assertEqual(redact_sensitive_values("plain text"), "plain text")

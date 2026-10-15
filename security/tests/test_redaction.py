from django.test import SimpleTestCase, override_settings

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


class NormalizedKeyTests(SimpleTestCase):
    def test_redacts_api_key_spellings(self):
        for key in ("api_key", "apiKey", "API-Key", "x-api-key", "APIKEY"):
            with self.subTest(key=key):
                redacted = redact_sensitive_values({key: "secret"})

                self.assertEqual(redacted[key], REDACTED_PLACEHOLDER)

    def test_redacts_every_sensitive_fragment(self):
        keys = (
            "passwd",
            "new_password",
            "id_token",
            "client_secret",
            "Authorization",
            "aws_credentials",
            "private_key",
            "privateKey",
        )
        for key in keys:
            with self.subTest(key=key):
                redacted = redact_sensitive_values({key: "secret"})

                self.assertEqual(redacted[key], REDACTED_PLACEHOLDER)

    def test_redacts_every_exact_sensitive_key(self):
        keys = ("otp", "OTP", "pin", "cvv", "cvc", "card_number", "cardNumber", "ssn")
        for key in keys:
            with self.subTest(key=key):
                redacted = redact_sensitive_values({key: "1234"})

                self.assertEqual(redacted[key], REDACTED_PLACEHOLDER)

    def test_keeps_keys_that_only_contain_an_exact_key(self):
        payload = {"shipping": "express", "pinned": True, "spinner": 1, "options": []}

        self.assertEqual(redact_sensitive_values(payload), payload)

    def test_redacts_new_keys_inside_nested_structures(self):
        payload = {"billing": {"cards": [{"cardNumber": "4111", "label": "main"}]}}

        redacted = redact_sensitive_values(payload)

        card = redacted["billing"]["cards"][0]
        self.assertEqual(card, {"cardNumber": REDACTED_PLACEHOLDER, "label": "main"})


class ExtraSensitiveKeysTests(SimpleTestCase):
    @override_settings(AUDIT_EXTRA_SENSITIVE_KEYS=["tax-id"])
    def test_redacts_extra_keys_in_any_spelling(self):
        for key in ("tax_id", "taxId", "TAX-ID"):
            with self.subTest(key=key):
                redacted = redact_sensitive_values({key: "20-12345678-9"})

                self.assertEqual(redacted[key], REDACTED_PLACEHOLDER)

    @override_settings(AUDIT_EXTRA_SENSITIVE_KEYS=["tax-id"])
    def test_extra_keys_match_whole_keys_only(self):
        payload = {"tax_identifier_type": "cuit"}

        self.assertEqual(redact_sensitive_values(payload), payload)

    @override_settings(AUDIT_EXTRA_SENSITIVE_KEYS=[])
    def test_no_extra_keys_by_default(self):
        self.assertEqual(redact_sensitive_values({"tax_id": "1"}), {"tax_id": "1"})

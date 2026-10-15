from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import SimpleTestCase, override_settings

from security.password_validation import CharacterClassValidator

ALL_CLASSES = ["uppercase", "lowercase", "digit", "symbol"]
PASSWORD_MISSING_ONLY = {
    "uppercase": "kestrel9quartz!",
    "lowercase": "KESTREL9QUARTZ!",
    "digit": "Kestrel-Quartz",
    "symbol": "Kestrel9Quartz",
}


def validators_requiring(classes):
    return [
        {
            "NAME": "security.password_validation.CharacterClassValidator",
            "OPTIONS": {"required_classes": classes},
        }
    ]


def error_codes_for(password):
    try:
        validate_password(password)
    except ValidationError as error:
        return [item.code for item in error.error_list]
    return []


class CharacterClassRuleTests(SimpleTestCase):
    def test_each_rule_rejects_when_required(self):
        for name, password in PASSWORD_MISSING_ONLY.items():
            with (
                self.subTest(rule=name),
                override_settings(
                    AUTH_PASSWORD_VALIDATORS=validators_requiring(ALL_CLASSES)
                ),
            ):
                self.assertEqual(error_codes_for(password), [f"password_no_{name}"])

    def test_each_rule_accepts_when_turned_off(self):
        for name, password in PASSWORD_MISSING_ONLY.items():
            others = [other for other in ALL_CLASSES if other != name]
            with (
                self.subTest(rule=name),
                override_settings(
                    AUTH_PASSWORD_VALIDATORS=validators_requiring(others)
                ),
            ):
                self.assertEqual(error_codes_for(password), [])

    def test_letters_outside_ascii_do_not_count(self):
        with override_settings(
            AUTH_PASSWORD_VALIDATORS=validators_requiring(ALL_CLASSES)
        ):
            codes = error_codes_for("Ñ9quartz€")

        self.assertEqual(codes, ["password_no_uppercase", "password_no_symbol"])


class CharacterClassValidatorTests(SimpleTestCase):
    def test_help_text_lists_only_the_required_classes(self):
        help_text = CharacterClassValidator(["digit", "symbol"]).get_help_text()

        self.assertIn("digit (0-9)", help_text)
        self.assertNotIn("uppercase", help_text)

    def test_rejects_an_unknown_class(self):
        with self.assertRaises(ImproperlyConfigured):
            CharacterClassValidator(["emoji"])


class DefaultPasswordPolicyTests(SimpleTestCase):
    def test_requires_eight_characters_and_every_class(self):
        codes = error_codes_for("kestrel")

        self.assertIn("password_too_short", codes)
        self.assertIn("password_no_uppercase", codes)
        self.assertIn("password_no_digit", codes)
        self.assertIn("password_no_symbol", codes)

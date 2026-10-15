import string
from dataclasses import dataclass

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class CharacterClass:
    name: str
    characters: str
    label: str

    def is_present_in(self, password):
        return any(character in self.characters for character in password)


# ASCII only, so a frontend can mirror the same rules with a plain regular expression.
CHARACTER_CLASSES = {
    character_class.name: character_class
    for character_class in (
        CharacterClass(
            "uppercase", string.ascii_uppercase, _("uppercase letter (A-Z)")
        ),
        CharacterClass(
            "lowercase", string.ascii_lowercase, _("lowercase letter (a-z)")
        ),
        CharacterClass("digit", string.digits, _("digit (0-9)")),
        CharacterClass("symbol", string.punctuation, _("symbol, such as ! ? # - _")),
    )
}


class CharacterClassValidator:
    def __init__(self, required_classes=tuple(CHARACTER_CLASSES)):
        unknown_classes = set(required_classes) - set(CHARACTER_CLASSES)
        if unknown_classes:
            raise ImproperlyConfigured(
                f"Unknown password character classes: {sorted(unknown_classes)}. "
                f"Valid ones: {list(CHARACTER_CLASSES)}."
            )
        self.required_classes = [CHARACTER_CLASSES[name] for name in required_classes]

    def validate(self, password, user=None):
        missing_classes = [
            character_class
            for character_class in self.required_classes
            if not character_class.is_present_in(password)
        ]
        if missing_classes:
            raise ValidationError(
                [build_missing_class_error(c) for c in missing_classes]
            )

    def get_help_text(self):
        if not self.required_classes:
            return ""
        labels = ", ".join(str(c.label) for c in self.required_classes)
        return format_lazy(
            _("Your password must contain at least one of each: {labels}."),
            labels=labels,
        )


def build_missing_class_error(character_class):
    return ValidationError(
        _("This password must contain at least one %(label)s."),
        code=f"password_no_{character_class.name}",
        params={"label": character_class.label},
    )

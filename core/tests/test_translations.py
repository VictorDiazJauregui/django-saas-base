import ast
import gettext
from dataclasses import dataclass, field
from pathlib import Path

from django.core import mail
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status

from security.tests.account_links import with_account_links
from security.tests.api_test_case import CacheResetAPITestCase
from security.tests.test_throttling import WRONG_PASSWORD, override_rates
from security.tests.user_factory import (
    DEFAULT_EMAIL,
    build_registration_payload,
    create_user,
)

LOCALE_DIR = Path(__file__).resolve().parents[2] / "locale" / "es" / "LC_MESSAGES"
PO_FILE, MO_FILE = LOCALE_DIR / "django.po", LOCALE_DIR / "django.mo"
NO_SYMBOL_PASSWORD = "Str0ngPassphrase42"
SPANISH = {"HTTP_ACCEPT_LANGUAGE": "es"}
ENGLISH = {"HTTP_ACCEPT_LANGUAGE": "en"}


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
@override_rates(login=None, register=None, password=None)
class SpanishApiMessagesTests(CacheResetAPITestCase):
    def register_without_symbol(self, headers):
        payload = build_registration_payload(
            password=NO_SYMBOL_PASSWORD, password2=NO_SYMBOL_PASSWORD
        )
        return self.client.post(
            reverse("security:register"), payload, format="json", **headers
        )

    def test_password_policy_error_in_spanish(self):
        response = self.register_without_symbol(SPANISH)

        self.assertEqual(
            response.data["fields"]["password"],
            ["La contraseña debe contener al menos: un símbolo, como ! ? # - _."],
        )

    def test_password_policy_error_stays_in_english(self):
        response = self.register_without_symbol(ENGLISH)

        self.assertEqual(
            response.data["fields"]["password"],
            ["This password must contain at least one symbol, such as ! ? # - _."],
        )

    def test_lockout_answer_in_spanish(self):
        create_user()
        attempt = {"email": DEFAULT_EMAIL, "password": WRONG_PASSWORD}
        for _ in range(5):
            response = self.client.post(
                reverse("security:login"), attempt, format="json", **SPANISH
            )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertTrue(
            response.data["detail"].startswith(
                "Demasiados intentos fallidos de inicio de sesión."
            )
        )

    @override_settings(ALLOW_PUBLIC_REGISTRATION=False)
    def test_closed_registration_in_spanish(self):
        response = self.register_without_symbol(SPANISH)

        self.assertEqual(
            response.data["detail"], "El registro público está desactivado."
        )

    @with_account_links()
    def test_password_reset_email_in_spanish(self):
        create_user()
        self.client.post(
            reverse("security:password_reset"),
            {"email": DEFAULT_EMAIL},
            format="json",
            **SPANISH,
        )

        message = mail.outbox[-1]
        self.assertEqual(message.subject, "Restablecer la contraseña")
        self.assertIn("restablecer la contraseña", message.body)


@dataclass
class CatalogEntry:
    context: str = ""
    msgid: str = ""
    plural: str = ""
    translations: dict = field(default_factory=dict)
    fuzzy: bool = False


def unquote(line):
    return ast.literal_eval(line[line.index('"') :])


def read_po_entries(path):
    entries, entry, keyword = [], CatalogEntry(), None
    for raw_line in path.read_text().splitlines() + [""]:
        line = raw_line.strip()
        if not line:
            entries, entry = entries + [entry], CatalogEntry()
        elif line.startswith("#,"):
            entry.fuzzy = "fuzzy" in line
        elif not line.startswith("#"):
            keyword = keyword if line.startswith('"') else line.split(" ", 1)[0]
            append_text(entry, keyword, unquote(line))
    return [entry for entry in entries if entry.msgid]


def append_text(entry, keyword, text):
    if keyword in ("msgctxt", "msgid", "msgid_plural"):
        name = {"msgctxt": "context", "msgid": "msgid", "msgid_plural": "plural"}[
            keyword
        ]
        setattr(entry, name, getattr(entry, name) + text)
        return
    index = keyword[7:-1] if keyword.startswith("msgstr[") else "0"
    entry.translations[index] = entry.translations.get(index, "") + text


def compiled_key(entry, index):
    msgid = f"{entry.context}\x04{entry.msgid}" if entry.context else entry.msgid
    return (msgid, int(index)) if entry.plural else msgid


# The .mo is versioned so nobody needs gettext to see the translations; these tests make sure
# nobody forgets to translate an entry or to recompile after editing the .po.
class SpanishCatalogTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.entries = read_po_entries(PO_FILE)

    def test_every_entry_is_translated(self):
        untranslated = [
            e.msgid for e in self.entries if not all(e.translations.values())
        ]

        self.assertEqual(untranslated, [])

    def test_no_entry_is_fuzzy(self):
        self.assertEqual([e.msgid for e in self.entries if e.fuzzy], [])

    def test_compiled_catalog_matches_the_source(self):
        with MO_FILE.open("rb") as compiled_file:
            compiled = gettext.GNUTranslations(compiled_file)._catalog

        for entry in self.entries:
            for index, translation in entry.translations.items():
                with self.subTest(msgid=entry.msgid, index=index):
                    self.assertEqual(
                        compiled.get(compiled_key(entry, index)), translation
                    )

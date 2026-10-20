from unittest import mock

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status

from core.environment import validate_totp_encryption_key
from core.tests.settings_subprocess import read_settings
from security.models import AuditLog, RecoveryCode, TotpDevice
from security.two_factor import RECOVERY_CODE_COUNT, hash_recovery_code

from .api_test_case import LanguageResetAPITestCase
from .test_throttling import override_rates
from .two_factor_helpers import (
    TEST_ENCRYPTION_KEY,
    current_code,
    enable_two_factor,
    forget_last_code,
    log_in,
    with_two_factor,
)
from .user_factory import DEFAULT_PASSWORD, create_user

WRONG_CODE = "000000"


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
@override_rates(login=None, mfa=None)
class TwoFactorTestCase(LanguageResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user()

    def post(self, name, payload=None):
        return self.client.post(
            reverse(f"security:{name}"), payload or {}, format="json"
        )

    def second_step(self, **factor):
        mfa_token = log_in(self.client).data["mfa_token"]
        return self.post("login_two_factor", {"mfa_token": mfa_token, **factor})


@with_two_factor(enabled=False)
class DisabledModuleTests(TwoFactorTestCase):
    def test_the_two_factor_routes_answer_404(self):
        self.client.force_authenticate(self.user)
        for name in ("totp_setup", "totp_confirm", "totp_disable", "recovery_codes"):
            with self.subTest(name=name):
                self.assertEqual(self.post(name).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.get(reverse("security:totp_status")).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.post("login_two_factor").status_code, status.HTTP_404_NOT_FOUND
        )

    def test_the_login_ignores_an_enrolled_device(self):
        with with_two_factor():
            enable_two_factor(self.client, self.user)

        response = log_in(self.client)

        self.assertEqual(set(response.data), {"access", "refresh"})


@with_two_factor()
class SetupTests(TwoFactorTestCase):
    def test_anonymous_gets_401(self):
        self.assertEqual(
            self.post("totp_setup").status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_returns_the_secret_and_the_uri_for_the_qr(self):
        self.client.force_authenticate(self.user)

        response = self.post("totp_setup")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        uri = response.data["otpauth_uri"]
        self.assertTrue(uri.startswith("otpauth://totp/Acme:jane.doe%40example.com?"))
        self.assertIn(f"secret={response.data['secret']}", uri)

    def test_the_secret_is_stored_encrypted(self):
        self.client.force_authenticate(self.user)
        secret = self.post("totp_setup").data["secret"]

        device = TotpDevice.objects.get(user=self.user)
        self.assertNotIn(secret, device.encrypted_secret)
        self.assertIsNone(device.confirmed_at)

    def test_a_new_setup_replaces_an_unconfirmed_one(self):
        self.client.force_authenticate(self.user)
        first = self.post("totp_setup").data["secret"]
        second = self.post("totp_setup").data["secret"]

        self.assertNotEqual(first, second)
        self.assertEqual(TotpDevice.objects.filter(user=self.user).count(), 1)

    def test_setup_with_two_factor_on_gets_409(self):
        enable_two_factor(self.client, self.user)
        self.client.force_authenticate(self.user)

        response = self.post("totp_setup")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "totp_already_enabled")


@with_two_factor()
class ConfirmTests(TwoFactorTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.user)

    def test_the_first_code_turns_it_on_and_returns_the_recovery_codes(self):
        secret = self.post("totp_setup").data["secret"]

        response = self.post("totp_confirm", {"otp": current_code(secret)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = response.data["recovery_codes"]
        self.assertEqual(len(codes), RECOVERY_CODE_COUNT)
        self.assertEqual(len(set(codes)), RECOVERY_CODE_COUNT)
        self.assertIsNotNone(TotpDevice.objects.get(user=self.user).confirmed_at)

    def test_the_device_and_the_codes_are_shown_by_their_user(self):
        secret = self.post("totp_setup").data["secret"]
        self.post("totp_confirm", {"otp": current_code(secret)})

        self.assertEqual(str(TotpDevice.objects.get()), self.user.email)
        self.assertEqual(str(RecoveryCode.objects.first()), self.user.email)

    def test_only_the_hashes_of_the_recovery_codes_are_stored(self):
        secret = self.post("totp_setup").data["secret"]
        codes = self.post("totp_confirm", {"otp": current_code(secret)}).data[
            "recovery_codes"
        ]

        stored = set(RecoveryCode.objects.values_list("code_hash", flat=True))
        self.assertEqual(stored, {hash_recovery_code(code) for code in codes})

    def test_a_wrong_code_gets_400(self):
        self.post("totp_setup")

        response = self.post("totp_confirm", {"otp": WRONG_CODE})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("otp", response.data["fields"])

    def test_without_a_setup_gets_400(self):
        response = self.post("totp_confirm", {"otp": WRONG_CODE})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("otp", response.data["fields"])

    def test_a_code_that_is_not_six_digits_gets_400(self):
        self.post("totp_setup")

        for otp in ("12345", "1234567", "abcdef", ""):
            with self.subTest(otp=otp):
                response = self.post("totp_confirm", {"otp": otp})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@with_two_factor()
class StatusTests(TwoFactorTestCase):
    def get_status(self):
        self.client.force_authenticate(self.user)
        return self.client.get(reverse("security:totp_status")).data

    def test_off_by_default(self):
        self.assertEqual(
            self.get_status(), {"enabled": False, "recovery_codes_left": 0}
        )

    def test_counts_the_unused_recovery_codes(self):
        codes = enable_two_factor(self.client, self.user)[1]
        self.second_step(recovery_code=codes[0])

        self.assertEqual(
            self.get_status(),
            {"enabled": True, "recovery_codes_left": RECOVERY_CODE_COUNT - 1},
        )


@with_two_factor()
class LoginChallengeTests(TwoFactorTestCase):
    def test_without_two_factor_the_login_is_unchanged(self):
        response = log_in(self.client)

        self.assertEqual(set(response.data), {"access", "refresh"})

    def test_with_two_factor_the_login_asks_for_the_code(self):
        enable_two_factor(self.client, self.user)

        response = log_in(self.client)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {"mfa_required", "mfa_token"})
        self.assertTrue(response.data["mfa_required"])

    def test_a_wrong_password_still_gets_401(self):
        enable_two_factor(self.client, self.user)

        response = log_in(self.client, password="Wrong-Passphrase-42")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_the_challenge_does_not_count_as_a_login(self):
        enable_two_factor(self.client, self.user)

        log_in(self.client)

        self.user.refresh_from_db()
        self.assertIsNone(self.user.last_login)

    def test_the_audit_log_records_the_user_of_the_challenge(self):
        enable_two_factor(self.client, self.user)

        log_in(self.client)

        record = AuditLog.objects.filter(path=reverse("security:login")).latest(
            "timestamp"
        )
        self.assertEqual(record.user, self.user)


@with_two_factor()
class SecondStepTests(TwoFactorTestCase):
    def setUp(self):
        super().setUp()
        self.secret, self.recovery_codes = enable_two_factor(self.client, self.user)

    def test_the_right_code_returns_the_tokens(self):
        response = self.second_step(otp=current_code(self.secret))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {"access", "refresh"})
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)

    def test_the_same_code_works_once(self):
        code = current_code(self.secret)
        self.second_step(otp=code)

        response = self.second_step(otp=code)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("otp", response.data["fields"])

    def test_a_wrong_code_gets_400(self):
        response = self.second_step(otp=WRONG_CODE)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_recovery_code_works_once(self):
        first = self.second_step(recovery_code=self.recovery_codes[0])
        second = self.second_step(recovery_code=self.recovery_codes[0])

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("recovery_code", second.data["fields"])

    def test_a_recovery_code_ignores_case_dashes_and_spaces(self):
        typed = f"  {self.recovery_codes[1].replace('-', ' ').upper()} "

        response = self.second_step(recovery_code=typed)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_both_factors_or_none_get_400(self):
        both = self.second_step(
            otp=current_code(self.secret), recovery_code=self.recovery_codes[0]
        )
        none = self.second_step()

        self.assertEqual(both.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(none.status_code, status.HTTP_400_BAD_REQUEST)

    def test_an_altered_token_gets_401(self):
        response = self.post(
            "login_two_factor",
            {"mfa_token": "not-a-token", "otp": current_code(self.secret)},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "invalid_mfa_token")

    def test_an_expired_token_gets_401(self):
        mfa_token = log_in(self.client).data["mfa_token"]

        with mock.patch("security.two_factor.MFA_TOKEN_MAX_AGE_SECONDS", -1):
            response = self.post(
                "login_two_factor",
                {"mfa_token": mfa_token, "otp": current_code(self.secret)},
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "invalid_mfa_token")

    def test_a_token_of_a_deactivated_user_gets_401(self):
        mfa_token = log_in(self.client).data["mfa_token"]
        self.user.is_active = False
        self.user.save()

        response = self.post(
            "login_two_factor",
            {"mfa_token": mfa_token, "otp": current_code(self.secret)},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_token_after_turning_two_factor_off_gets_401(self):
        mfa_token = log_in(self.client).data["mfa_token"]
        TotpDevice.objects.filter(user=self.user).delete()

        response = self.post(
            "login_two_factor", {"mfa_token": mfa_token, "otp": WRONG_CODE}
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_five_wrong_codes_block_the_next_tries(self):
        for _ in range(5):
            self.second_step(otp=WRONG_CODE)

        response = self.second_step(otp=current_code(self.secret))

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data["code"], "too_many_code_attempts")
        self.assertIn("Retry-After", response)

    def test_the_audit_log_hides_the_codes_and_the_token(self):
        self.second_step(recovery_code=self.recovery_codes[2])

        record = AuditLog.objects.get(path=reverse("security:login_two_factor"))
        self.assertEqual(record.user, self.user)
        self.assertEqual(record.payload["recovery_code"], "[REDACTED]")
        self.assertEqual(record.payload["mfa_token"], "[REDACTED]")

    def test_a_secret_encrypted_with_another_key_is_rejected_and_logged(self):
        other_key = Fernet.generate_key().decode()
        with override_settings(TOTP_ENCRYPTION_KEY=other_key):
            with self.assertLogs("security.two_factor", level="ERROR"):
                response = self.second_step(otp=current_code(self.secret))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@with_two_factor()
class DisableTests(TwoFactorTestCase):
    def setUp(self):
        super().setUp()
        self.secret = enable_two_factor(self.client, self.user)[0]
        self.client.force_authenticate(self.user)

    def test_password_and_code_turn_it_off(self):
        response = self.post(
            "totp_disable",
            {"password": DEFAULT_PASSWORD, "otp": current_code(self.secret)},
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TotpDevice.objects.filter(user=self.user).exists())
        self.assertFalse(RecoveryCode.objects.filter(user=self.user).exists())
        self.client.force_authenticate(None)
        self.assertEqual(set(log_in(self.client).data), {"access", "refresh"})

    def test_a_wrong_password_gets_400(self):
        response = self.post(
            "totp_disable",
            {"password": "Wrong-Passphrase-42", "otp": current_code(self.secret)},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data["fields"])
        self.assertTrue(TotpDevice.objects.filter(user=self.user).exists())

    def test_a_wrong_code_gets_400(self):
        response = self.post(
            "totp_disable", {"password": DEFAULT_PASSWORD, "otp": WRONG_CODE}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(TotpDevice.objects.filter(user=self.user).exists())

    def test_without_two_factor_gets_409(self):
        TotpDevice.objects.filter(user=self.user).delete()

        response = self.post(
            "totp_disable", {"password": DEFAULT_PASSWORD, "otp": WRONG_CODE}
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "totp_not_enabled")


@with_two_factor()
class RecoveryCodeRegenerationTests(TwoFactorTestCase):
    def test_new_codes_replace_the_old_ones(self):
        secret, old_codes = enable_two_factor(self.client, self.user)
        self.client.force_authenticate(self.user)

        response = self.post("recovery_codes", {"otp": current_code(secret)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_codes = response.data["recovery_codes"]
        self.assertFalse(set(old_codes) & set(new_codes))
        self.client.force_authenticate(None)
        forget_last_code(self.user)
        self.assertEqual(
            self.second_step(recovery_code=old_codes[0]).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.second_step(recovery_code=new_codes[0]).status_code,
            status.HTTP_200_OK,
        )


@with_two_factor()
@override_rates(login=None, mfa="2/m")
class MfaThrottleTests(TwoFactorTestCase):
    def test_the_second_step_has_its_own_limit(self):
        enable_two_factor(self.client, self.user)
        for _ in range(2):
            self.second_step(otp=WRONG_CODE)

        response = self.second_step(otp=WRONG_CODE)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data["code"], "throttled")


class EncryptionKeyValidationTests(SimpleTestCase):
    def test_a_disabled_module_needs_no_key(self):
        self.assertEqual(validate_totp_encryption_key("", enabled=False), "")

    def test_an_enabled_module_needs_a_key(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "TOTP_ENCRYPTION_KEY"):
            validate_totp_encryption_key("", enabled=True)

    def test_the_key_must_be_a_fernet_key(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "TOTP_ENCRYPTION_KEY"):
            validate_totp_encryption_key("not-a-key", enabled=True)

    def test_a_fernet_key_is_accepted(self):
        self.assertEqual(
            validate_totp_encryption_key(TEST_ENCRYPTION_KEY, enabled=True),
            TEST_ENCRYPTION_KEY,
        )

    def test_the_settings_read_the_module_flags(self):
        values = read_settings(
            ["TOTP_ENABLED", "TOTP_ISSUER"],
            TOTP_ENABLED="True",
            TOTP_ENCRYPTION_KEY=TEST_ENCRYPTION_KEY,
            TOTP_ISSUER="Acme",
        )

        self.assertEqual(values, {"TOTP_ENABLED": True, "TOTP_ISSUER": "Acme"})

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from security.models import RecoveryCode, TotpDevice

from .two_factor_helpers import (
    current_code,
    enable_two_factor,
    forget_last_code,
    with_two_factor,
)
from .user_factory import DEFAULT_PASSWORD, create_superuser, create_user

LOGIN_URL = reverse("admin:login")
INDEX_URL = reverse("admin:index")
WRONG_CODE = "000000"


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class TwoFactorAdminTestCase(TestCase):
    def setUp(self):
        self.staff = create_superuser()

    def log_in(self, **extra):
        payload = {"username": self.staff.email, "password": DEFAULT_PASSWORD, **extra}
        return self.client.post(f"{LOGIN_URL}?next={INDEX_URL}", payload)

    def enable_two_factor(self):
        return enable_two_factor(APIClient(), self.staff)


@with_two_factor()
class AdminLoginTests(TwoFactorAdminTestCase):
    def test_the_form_shows_the_code_field(self):
        self.assertContains(self.client.get(LOGIN_URL), 'name="otp"')

    def test_without_two_factor_the_password_is_enough(self):
        response = self.log_in()

        self.assertRedirects(response, INDEX_URL)

    def test_with_two_factor_the_password_alone_is_refused(self):
        self.enable_two_factor()

        response = self.log_in()

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Enter a valid code of your app or a recovery code."
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_with_two_factor_a_wrong_code_is_refused(self):
        self.enable_two_factor()

        response = self.log_in(otp=WRONG_CODE)

        self.assertContains(
            response, "Enter a valid code of your app or a recovery code."
        )

    def test_with_two_factor_the_right_code_logs_in(self):
        secret = self.enable_two_factor()[0]

        response = self.log_in(otp=current_code(secret))

        self.assertRedirects(response, INDEX_URL)

    def test_a_recovery_code_logs_in_once(self):
        codes = self.enable_two_factor()[1]

        self.assertRedirects(self.log_in(otp=codes[0]), INDEX_URL)
        self.client.logout()

        self.assertEqual(self.log_in(otp=codes[0]).status_code, 200)

    def test_five_wrong_codes_block_the_form(self):
        secret = self.enable_two_factor()[0]
        for _ in range(5):
            self.log_in(otp=WRONG_CODE)

        response = self.log_in(otp=current_code(secret))

        self.assertContains(
            response, "Too many wrong codes. Try again in a few minutes."
        )

    def test_a_wrong_password_shows_the_usual_error(self):
        self.enable_two_factor()

        response = self.log_in(password="Wrong-Passphrase-42")

        self.assertContains(
            response, "Please enter the correct email address and password"
        )


@with_two_factor(enabled=False)
class DisabledModuleAdminLoginTests(TwoFactorAdminTestCase):
    def test_the_form_has_no_code_field(self):
        self.assertNotContains(self.client.get(LOGIN_URL), 'name="otp"')

    def test_an_enrolled_device_is_ignored(self):
        with with_two_factor():
            self.enable_two_factor()

        self.assertRedirects(self.log_in(), INDEX_URL)


@with_two_factor()
class UserAdminTwoFactorTests(TestCase):
    def setUp(self):
        self.superuser = create_superuser()
        self.user = create_user()
        enable_two_factor(APIClient(), self.user)
        forget_last_code(self.user)
        self.client.force_login(self.superuser)

    def test_the_list_shows_who_has_two_factor(self):
        response = self.client.get(reverse("admin:security_user_changelist"))

        self.assertContains(response, "Two-factor")
        self.assertContains(response, 'alt="True"')

    def test_the_action_turns_it_off(self):
        response = self.client.post(
            reverse("admin:security_user_changelist"),
            {
                "action": "turn_off_two_factor",
                "_selected_action": [str(self.user.pk), str(self.superuser.pk)],
            },
            follow=True,
        )

        self.assertContains(
            response, "Two-factor authentication turned off for 1 user."
        )
        self.assertFalse(TotpDevice.objects.filter(user=self.user).exists())
        self.assertFalse(RecoveryCode.objects.filter(user=self.user).exists())

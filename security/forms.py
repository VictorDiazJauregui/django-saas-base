from django import forms
from django.conf import settings
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _

from .two_factor import TooManyCodeAttempts, requires_second_factor, verify_typed_code

User = get_user_model()


class EmailUserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email",)


class EmailUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class TwoFactorAdminAuthenticationForm(AdminAuthenticationForm):
    otp = forms.CharField(
        label=_("Authentication code"),
        required=False,
        max_length=32,
        strip=True,
        help_text=_(
            "Only with two-factor authentication on: the code of your app or a "
            "recovery code."
        ),
    )
    error_messages = {
        **AdminAuthenticationForm.error_messages,
        "second_factor": _("Enter a valid code of your app or a recovery code."),
        "too_many_codes": _("Too many wrong codes. Try again in a few minutes."),
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        if not settings.TOTP_ENABLED:
            del self.fields["otp"]

    # Runs after the password matched, so the code is only checked for the right account.
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not requires_second_factor(user):
            return
        typed_code = self.cleaned_data.get("otp", "")
        if not typed_code:
            raise forms.ValidationError(
                self.error_messages["second_factor"], "second_factor"
            )
        self.check_typed_code(user, typed_code)

    def check_typed_code(self, user, typed_code):
        try:
            accepted = verify_typed_code(user, typed_code)
        except TooManyCodeAttempts as error:
            raise forms.ValidationError(
                self.error_messages["too_many_codes"], "too_many_codes"
            ) from error
        if not accepted:
            raise forms.ValidationError(
                self.error_messages["second_factor"], "second_factor"
            )

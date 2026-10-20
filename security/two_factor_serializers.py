from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .two_factor import (
    find_mfa_token_owner,
    find_pending_device,
    verify_second_factor,
    verify_setup_code,
)

INVALID_CODE_MESSAGE = _("Invalid or expired code.")
SETUP_NOT_STARTED_MESSAGE = _("Start the setup first.")
ONE_FACTOR_MESSAGE = _("Send either otp or recovery_code.")


class OtpField(serializers.RegexField):
    def __init__(self, **kwargs):
        super().__init__(
            r"^\d{6}$",
            max_length=6,
            error_messages={"invalid": INVALID_CODE_MESSAGE},
            **kwargs,
        )


class TotpConfirmSerializer(serializers.Serializer):
    otp = OtpField(write_only=True)

    def validate(self, attrs):
        device = find_pending_device(self.context["request"].user)
        if device is None:
            raise serializers.ValidationError({"otp": [SETUP_NOT_STARTED_MESSAGE]})
        if not verify_setup_code(device, attrs["otp"]):
            raise serializers.ValidationError({"otp": [INVALID_CODE_MESSAGE]})
        return {"device": device}


class SecondFactorSerializer(serializers.Serializer):
    otp = OtpField(write_only=True, required=False)
    recovery_code = serializers.CharField(
        write_only=True, required=False, max_length=32
    )

    def validate(self, attrs):
        if bool(attrs.get("otp")) == bool(attrs.get("recovery_code")):
            raise serializers.ValidationError(ONE_FACTOR_MESSAGE)
        user = self.find_factor_owner(attrs)
        if not verify_second_factor(user, attrs.get("otp"), attrs.get("recovery_code")):
            field = "otp" if attrs.get("otp") else "recovery_code"
            raise serializers.ValidationError({field: [INVALID_CODE_MESSAGE]})
        return {**attrs, "user": user}

    def find_factor_owner(self, attrs):
        return self.context["request"].user


class MfaLoginSerializer(SecondFactorSerializer):
    mfa_token = serializers.CharField(write_only=True)

    def find_factor_owner(self, attrs):
        return find_mfa_token_owner(attrs["mfa_token"])


class TotpDisableSerializer(SecondFactorSerializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError(_("Your current password is incorrect."))
        return value


class TotpSetupSerializer(serializers.Serializer):
    secret = serializers.CharField(read_only=True)
    otpauth_uri = serializers.CharField(read_only=True)


class RecoveryCodesSerializer(serializers.Serializer):
    recovery_codes = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )


class TotpStatusSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(read_only=True)
    recovery_codes_left = serializers.IntegerField(read_only=True)

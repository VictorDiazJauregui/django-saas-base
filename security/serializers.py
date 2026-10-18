from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)

from .email_verification import find_user_to_verify
from .frontend_links import INVALID_LINK_MESSAGE
from .login_lockout import raise_if_locked_out
from .password_reset import find_user_for_reset
from .registration import register_account

User = get_user_model()
REGISTRATION_ANSWER_FIELDS = ("email", "first_name", "last_name")


class UserRegisterSerializer(serializers.ModelSerializer):
    # Replaces the UniqueValidator DRF builds from unique=True, which compares case-sensitively.
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, required=True)
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ("email", "password", "password2", "first_name", "last_name")
        extra_kwargs = {
            "first_name": {"required": True},
            "last_name": {"required": True},
        }

    def validate_email(self, value):
        return User.objects.normalize_email(value)

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password": _("Password fields didn't match.")}
            )
        validate_password_for_new_user(attrs)
        return attrs

    # The answer is built from the submitted data, never from a stored account, so a new and
    # an existing email get the same body.
    def create(self, validated_data):
        validated_data.pop("password2")
        register_account(validated_data)
        answer = {field: validated_data[field] for field in REGISTRATION_ANSWER_FIELDS}
        return User(**answer)


def validate_password_for_new_user(attrs):
    # An unsaved user lets the similarity validator compare the password with the email and name.
    unsaved_user = User(
        email=attrs["email"],
        first_name=attrs["first_name"],
        last_name=attrs["last_name"],
    )
    try:
        validate_password(attrs["password"], user=unsaved_user)
    except DjangoValidationError as error:
        raise serializers.ValidationError({"password": error.messages}) from error


def validate_new_password(password, user):
    try:
        validate_password(password, user=user)
    except DjangoValidationError as error:
        raise serializers.ValidationError({"new_password": error.messages}) from error


class NewPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    new_password2 = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password2"]:
            raise serializers.ValidationError(
                {"new_password2": _("Password fields didn't match.")}
            )
        validate_new_password(attrs["new_password"], self.find_password_owner(attrs))
        return attrs

    def find_password_owner(self, attrs):
        raise NotImplementedError


class PasswordChangeSerializer(NewPasswordSerializer):
    current_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError(_("Your current password is incorrect."))
        return value

    def find_password_owner(self, attrs):
        return self.context["request"].user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(NewPasswordSerializer):
    uid = serializers.CharField()
    token = serializers.CharField(write_only=True)

    # A broken uid and a used, expired or altered token get the same error, so the answer
    # tells nothing about which accounts exist.
    def validate(self, attrs):
        user = find_user_for_reset(attrs["uid"], attrs["token"])
        if user is None:
            raise serializers.ValidationError({"token": [INVALID_LINK_MESSAGE]})
        return super().validate({**attrs, "user": user})

    def find_password_owner(self, attrs):
        return attrs["user"]


class EmailVerificationSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = find_user_to_verify(attrs["uid"], attrs["token"])
        if user is None:
            raise serializers.ValidationError({"token": [INVALID_LINK_MESSAGE]})
        return {**attrs, "user": user}


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "date_joined")
        read_only_fields = ("id", "email", "date_joined")


class ExistingUserTokenRefreshSerializer(TokenRefreshSerializer):
    # SimpleJWT looks the user up without catching DoesNotExist, so a valid refresh token
    # of a deleted user ended in a 500. It gets the same 401 as an inactive user instead.
    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except User.DoesNotExist as error:
            raise AuthenticationFailed(
                self.error_messages["no_active_account"], "no_active_account"
            ) from error


class LockoutAwareTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except AuthenticationFailed:
            raise_if_locked_out(self.context["request"])
            raise

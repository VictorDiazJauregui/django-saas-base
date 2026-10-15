from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

User = get_user_model()


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
        email = User.objects.normalize_email(value)
        if User.objects.is_email_taken(email):
            raise serializers.ValidationError(
                _("user with this email address already exists.")
            )
        return email

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password": _("Password fields didn't match.")}
            )
        validate_password_for_new_user(attrs)
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        return User.objects.create_user(**validated_data)


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

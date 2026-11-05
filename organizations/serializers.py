from datetime import datetime

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import Invitation, Membership, Organization, OrganizationApiKey
from .roles import ORGANIZATION_API_KEY_ROLES, OrganizationRole


class OrganizationSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "role", "created_at"]
        read_only_fields = ["id", "role", "created_at"]
        extra_kwargs = {"slug": {"required": False}}

    def get_role(self, organization) -> str:
        return self.context["role"]


class MyOrganizationSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="organization.id")
    name = serializers.CharField(source="organization.name")
    slug = serializers.CharField(source="organization.slug")
    created_at = serializers.DateTimeField(source="organization.created_at")

    class Meta:
        model = Membership
        fields = ["id", "name", "slug", "role", "created_at"]
        read_only_fields = fields


class MemberUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ["id", "email", "first_name", "last_name"]
        read_only_fields = fields


class MemberSerializer(serializers.ModelSerializer):
    user = MemberUserSerializer(read_only=True)
    role = serializers.ChoiceField(choices=OrganizationRole.choices)

    class Meta:
        model = Membership
        fields = ["id", "user", "role", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class InvitationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(choices=OrganizationRole.choices)
    invited_by_email = serializers.EmailField(
        source="invited_by.email", read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = Invitation
        fields = ["id", "email", "role", "invited_by_email", "expires_at", "created_at"]
        read_only_fields = ["id", "invited_by_email", "expires_at", "created_at"]

    def validate_email(self, value):
        return get_user_model().objects.normalize_email(value)


class InvitationTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=100, write_only=True)


class InvitedOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug"]
        read_only_fields = fields


class InvitationLookupSerializer(serializers.Serializer):
    organization = InvitedOrganizationSerializer(source="invitation.organization")
    email = serializers.EmailField(source="invitation.email")
    role = serializers.CharField(source="invitation.role")
    expires_at = serializers.DateTimeField(source="invitation.expires_at")
    account_exists = serializers.BooleanField()


class InvitationRegisterSerializer(InvitationTokenSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password": _("Password fields didn't match.")}
            )
        return attrs


class OrganizationApiKeySerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=ORGANIZATION_API_KEY_ROLES)
    created_by_email = serializers.EmailField(
        source="created_by.email", read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = OrganizationApiKey
        fields = [
            "id",
            "name",
            "prefix",
            "role",
            "created_by_email",
            "expires_at",
            "last_used_at",
            "revoked_at",
            "created_at",
        ]
        read_only_fields = ["id", "prefix", "last_used_at", "revoked_at", "created_at"]

    def validate_expires_at(self, value: datetime | None) -> datetime | None:
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError(
                _("The expiry date must be in the future.")
            )
        return value


# The key travels only in the answer to its creation; it is never stored, so it can't be listed.
class CreatedOrganizationApiKeySerializer(OrganizationApiKeySerializer):
    api_key = serializers.SerializerMethodField()

    class Meta(OrganizationApiKeySerializer.Meta):
        fields = [*OrganizationApiKeySerializer.Meta.fields, "api_key"]

    def get_api_key(self, api_key: OrganizationApiKey) -> str:
        return self.context["raw_key"]

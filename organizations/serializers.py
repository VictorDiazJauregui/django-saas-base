from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import Invitation, Membership, Organization
from .roles import OrganizationRole


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

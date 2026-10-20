from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers

from core.api_schema import RETRY_AFTER_HEADER, DetailMessageSerializer, error_responses

from .serializers import ProfileSerializer, UserRegisterSerializer

AUTH_TAG = "auth"
ACCOUNT_TAG = "account"
EXAMPLE_EMAIL = "jane@example.com"
EXAMPLE_PASSWORD = "Str0ng-Passphrase-42"  # noqa: S105 - shown in the docs only
EXAMPLE_ACCESS = "eyJhbGciOiJIUzI1NiJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIn0.signature"
EXAMPLE_REFRESH = "eyJhbGciOiJIUzI1NiJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCJ9.signature"
EXAMPLE_UID = "OGY0MTlhZmYtNDllYy00ZjQyLWI5YjYtMGQ4ZmFhNzYxOTlj"
EXAMPLE_TOKEN = (
    "cz8k1x-4f9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d"  # noqa: S105 - shown in the docs only
)

TOKEN_PAIR = inline_serializer(
    "TokenPair",
    {"access": serializers.CharField(), "refresh": serializers.CharField()},
)
LOGIN = inline_serializer(
    "Login",
    {"email": serializers.EmailField(), "password": serializers.CharField()},
)
REFRESH_TOKEN = inline_serializer("RefreshToken", {"refresh": serializers.CharField()})
NEW_PASSWORD = {"new_password": EXAMPLE_PASSWORD, "new_password2": EXAMPLE_PASSWORD}


def request_example(value):
    return OpenApiExample("request", value=value, request_only=True)


def detail_response(message):
    example = OpenApiExample("sent", value={"detail": message}, response_only=True)
    return OpenApiResponse(DetailMessageSerializer, examples=[example])


TOKEN_PAIR_RESPONSE = OpenApiResponse(
    TOKEN_PAIR,
    examples=[
        OpenApiExample(
            "tokens",
            value={"access": EXAMPLE_ACCESS, "refresh": EXAMPLE_REFRESH},
            response_only=True,
        )
    ],
)

LOGIN_ANSWER = inline_serializer(
    "LoginAnswer",
    {
        "access": serializers.CharField(required=False),
        "refresh": serializers.CharField(required=False),
        "mfa_required": serializers.BooleanField(required=False),
        "mfa_token": serializers.CharField(required=False),
    },
)
LOGIN_ANSWER_RESPONSE = OpenApiResponse(
    LOGIN_ANSWER,
    examples=[
        OpenApiExample(
            "tokens",
            value={"access": EXAMPLE_ACCESS, "refresh": EXAMPLE_REFRESH},
            response_only=True,
        ),
        OpenApiExample(
            "second factor",
            value={"mfa_required": True, "mfa_token": "IjhmNDE5YWZmIg:1tE3x0:Yp2v0n4h"},
            response_only=True,
        ),
    ],
)

register_schema = extend_schema(
    tags=[AUTH_TAG],
    summary=_("Register a user"),
    description=_(
        "Answers 201 with the same body whether the email is new or already registered."
    ),
    auth=[],
    parameters=[RETRY_AFTER_HEADER],
    examples=[
        request_example(
            {
                "email": EXAMPLE_EMAIL,
                "password": EXAMPLE_PASSWORD,
                "password2": EXAMPLE_PASSWORD,
                "first_name": "Jane",
                "last_name": "Doe",
            }
        )
    ],
    responses={
        201: UserRegisterSerializer,
        **error_responses(
            "invalid", "token_not_valid", "permission_denied", "throttled"
        ),
    },
)

login_schema = extend_schema(
    tags=[AUTH_TAG],
    summary=_("Log in"),
    description=_(
        "Returns an access and a refresh token. Repeated failures lock the account "
        "for a while and answer 429 with the code account_locked_out. A user with "
        "two-factor authentication gets mfa_required and an mfa_token instead, for "
        "POST /api/v1/auth/login/2fa/."
    ),
    request=LOGIN,
    parameters=[RETRY_AFTER_HEADER],
    examples=[request_example({"email": EXAMPLE_EMAIL, "password": EXAMPLE_PASSWORD})],
    responses={
        200: LOGIN_ANSWER_RESPONSE,
        **error_responses(
            "invalid", "no_active_account", "throttled", "account_locked_out"
        ),
    },
)

refresh_schema = extend_schema(
    tags=[AUTH_TAG],
    summary=_("Get a new token pair"),
    description=_("The refresh token sent stops working."),
    request=REFRESH_TOKEN,
    examples=[request_example({"refresh": EXAMPLE_REFRESH})],
    responses={
        200: TOKEN_PAIR_RESPONSE,
        **error_responses("invalid", "token_not_valid", "no_active_account"),
    },
)

logout_schema = extend_schema(
    tags=[AUTH_TAG],
    summary=_("Log out"),
    description=_("Blacklists the refresh token sent. Answers an empty object."),
    request=REFRESH_TOKEN,
    examples=[request_example({"refresh": EXAMPLE_REFRESH})],
    responses={
        200: OpenApiResponse(
            OpenApiTypes.OBJECT,
            examples=[OpenApiExample("logged out", value={}, response_only=True)],
        ),
        **error_responses("invalid", "token_not_valid"),
    },
)

profile_read_schema = extend_schema(
    tags=[ACCOUNT_TAG],
    summary=_("Get your profile"),
    responses={
        200: ProfileSerializer,
        **error_responses("not_authenticated", "token_not_valid"),
    },
)

profile_update_schema = extend_schema(
    tags=[ACCOUNT_TAG],
    summary=_("Update your first and last name"),
    examples=[request_example({"first_name": "Jane", "last_name": "Doe"})],
    responses={
        200: ProfileSerializer,
        **error_responses("invalid", "not_authenticated", "token_not_valid"),
    },
)

password_change_schema = extend_schema(
    tags=[ACCOUNT_TAG],
    summary=_("Change your password"),
    description=_(
        "Every refresh token of the account stops working, this one included."
    ),
    parameters=[RETRY_AFTER_HEADER],
    examples=[
        request_example({"current_password": "Old-Passphrase-41", **NEW_PASSWORD})
    ],
    responses={
        204: None,
        **error_responses(
            "invalid", "not_authenticated", "token_not_valid", "throttled"
        ),
    },
)


# The message comes from the view, so the example is the answer the API really sends.
def document_password_reset(view):
    return extend_schema(
        tags=[ACCOUNT_TAG],
        summary=_("Email a password reset link"),
        description=_(
            "Answers the same whether the email belongs to an account or not."
        ),
        parameters=[RETRY_AFTER_HEADER],
        examples=[request_example({"email": EXAMPLE_EMAIL})],
        responses={
            200: detail_response(view.answer),
            **error_responses("invalid", "throttled"),
        },
    )(view)


password_reset_confirm_schema = extend_schema(
    tags=[ACCOUNT_TAG],
    summary=_("Set a new password with the link of the email"),
    parameters=[RETRY_AFTER_HEADER],
    examples=[
        request_example({"uid": EXAMPLE_UID, "token": EXAMPLE_TOKEN, **NEW_PASSWORD})
    ],
    responses={204: None, **error_responses("invalid", "throttled")},
)

verify_email_schema = extend_schema(
    tags=[ACCOUNT_TAG],
    summary=_("Verify an email with the link of the email"),
    parameters=[RETRY_AFTER_HEADER],
    examples=[request_example({"uid": EXAMPLE_UID, "token": EXAMPLE_TOKEN})],
    responses={204: None, **error_responses("invalid", "throttled")},
)


def document_resend_verification(view):
    return extend_schema(
        tags=[ACCOUNT_TAG],
        summary=_("Email a new verification link"),
        description=_("Answers the same whatever the state of the account."),
        parameters=[RETRY_AFTER_HEADER],
        examples=[request_example({"email": EXAMPLE_EMAIL})],
        responses={
            200: detail_response(view.answer),
            **error_responses("invalid", "throttled"),
        },
    )(view)

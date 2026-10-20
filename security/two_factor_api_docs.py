from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from core.api_schema import RETRY_AFTER_HEADER, error_responses

from .api_docs import AUTH_TAG, TOKEN_PAIR_RESPONSE, request_example
from .two_factor_serializers import (
    RecoveryCodesSerializer,
    TotpSetupSerializer,
    TotpStatusSerializer,
)

TWO_FACTOR_TAG = "two-factor"
EXAMPLE_CODE = "492039"
EXAMPLE_RECOVERY_CODE = "3f9a-07c1-b2e4-8d56"
EXAMPLE_MFA_TOKEN = "IjhmNDE5YWZmIg:1tE3x0:Yp2v0n4hJqzq8c1L0sV7m3k9wQe"  # noqa: S105 - shown in the docs only
MODULE_OFF = _("Answers 404 unless TOTP_ENABLED=True.")
FACTOR_EXAMPLES = [
    request_example({"otp": EXAMPLE_CODE}),
    OpenApiExample(
        "recovery code",
        value={"recovery_code": EXAMPLE_RECOVERY_CODE},
        request_only=True,
    ),
]


def recovery_codes_response():
    example = OpenApiExample(
        "codes", value={"recovery_codes": [EXAMPLE_RECOVERY_CODE]}, response_only=True
    )
    return OpenApiResponse(RecoveryCodesSerializer, examples=[example])


totp_status_schema = extend_schema(
    tags=[TWO_FACTOR_TAG],
    summary=_("Get the two-factor state"),
    description=MODULE_OFF,
    responses={
        200: TotpStatusSerializer,
        **error_responses("not_authenticated", "token_not_valid", "not_found"),
    },
)

totp_setup_schema = extend_schema(
    tags=[TWO_FACTOR_TAG],
    summary=_("Start the two-factor setup"),
    description=_(
        "Returns the secret and the otpauth URI for the QR. Nothing changes until the "
        "first code confirms it. "
    )
    + MODULE_OFF,
    request=None,
    responses={
        200: TotpSetupSerializer,
        **error_responses(
            "not_authenticated", "token_not_valid", "not_found", "totp_already_enabled"
        ),
    },
)

totp_confirm_schema = extend_schema(
    tags=[TWO_FACTOR_TAG],
    summary=_("Turn on two-factor authentication with the first code"),
    description=_("The recovery codes are shown only in this answer. ") + MODULE_OFF,
    parameters=[RETRY_AFTER_HEADER],
    examples=[request_example({"otp": EXAMPLE_CODE})],
    responses={
        200: recovery_codes_response(),
        **error_responses(
            "invalid",
            "not_authenticated",
            "token_not_valid",
            "not_found",
            "throttled",
            "too_many_code_attempts",
        ),
    },
)

totp_disable_schema = extend_schema(
    tags=[TWO_FACTOR_TAG],
    summary=_("Turn off two-factor authentication"),
    description=_("Needs the password and a code or a recovery code. ") + MODULE_OFF,
    parameters=[RETRY_AFTER_HEADER],
    examples=[
        request_example({"password": "Str0ng-Passphrase-42", "otp": EXAMPLE_CODE})
    ],
    responses={
        204: None,
        **error_responses(
            "invalid",
            "not_authenticated",
            "token_not_valid",
            "not_found",
            "totp_not_enabled",
            "throttled",
            "too_many_code_attempts",
        ),
    },
)

recovery_codes_schema = extend_schema(
    tags=[TWO_FACTOR_TAG],
    summary=_("Replace the recovery codes"),
    description=_("The old codes stop working. ") + MODULE_OFF,
    parameters=[RETRY_AFTER_HEADER],
    examples=FACTOR_EXAMPLES,
    responses={
        200: recovery_codes_response(),
        **error_responses(
            "invalid",
            "not_authenticated",
            "token_not_valid",
            "not_found",
            "totp_not_enabled",
            "throttled",
            "too_many_code_attempts",
        ),
    },
)

login_two_factor_schema = extend_schema(
    tags=[AUTH_TAG],
    summary=_("Finish a login with the second factor"),
    description=_(
        "Takes the mfa_token of the login, valid for 5 minutes, and a code or a "
        "recovery code. "
    )
    + MODULE_OFF,
    auth=[],
    parameters=[RETRY_AFTER_HEADER],
    examples=[
        request_example({"mfa_token": EXAMPLE_MFA_TOKEN, "otp": EXAMPLE_CODE}),
        OpenApiExample(
            "recovery code",
            value={
                "mfa_token": EXAMPLE_MFA_TOKEN,
                "recovery_code": EXAMPLE_RECOVERY_CODE,
            },
            request_only=True,
        ),
    ],
    responses={
        200: TOKEN_PAIR_RESPONSE,
        **error_responses(
            "invalid",
            "invalid_mfa_token",
            "not_found",
            "throttled",
            "too_many_code_attempts",
        ),
    },
)

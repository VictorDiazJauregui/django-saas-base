from functools import lru_cache

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException, PermissionDenied

from .account_events import USER_REGISTERED, emit_account_event
from .models import ExternalIdentity
from .permissions import PublicRegistrationEnabled
from .token_revocation import revoke_refresh_tokens

GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
GMAIL_DOMAIN = "@gmail.com"
REQUIRED_CLAIMS = ("exp", "iat", "iss", "aud", "sub", "email")
# Google rotates its keys every few weeks: an hour of cache saves a request per login.
JWKS_CACHE_SECONDS = 3600
JWKS_TIMEOUT_SECONDS = 10


# Not AuthenticationFailed: DRF turns that one into a 403 on a view without authentication
# classes, and this view has none.
class InvalidGoogleToken(APIException):
    status_code = 401
    default_detail = _("The Google sign-in is not valid. Try again.")
    default_code = "invalid_google_token"


class GoogleUnavailable(APIException):
    status_code = 503
    default_detail = _("Google can't be reached right now. Try again in a moment.")
    default_code = "google_unavailable"


class AccountExists(APIException):
    status_code = 409
    default_detail = _(
        "An account with this email already exists. Log in with its password."
    )
    default_code = "account_exists"


class InactiveAccount(APIException):
    status_code = 401
    default_detail = _("No active account found with the given credentials")
    default_code = "no_active_account"


@lru_cache(maxsize=4)
def build_jwks_client(url):
    return jwt.PyJWKClient(
        url, lifespan=JWKS_CACHE_SECONDS, timeout=JWKS_TIMEOUT_SECONDS
    )


def find_signing_key(id_token):
    try:
        return build_jwks_client(settings.GOOGLE_JWKS_URL).get_signing_key_from_jwt(
            id_token
        )
    except jwt.PyJWKClientConnectionError as error:
        raise GoogleUnavailable from error
    except (jwt.PyJWKClientError, jwt.DecodeError) as error:
        raise InvalidGoogleToken from error


def verify_google_id_token(id_token):
    signing_key = find_signing_key(id_token)
    try:
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_IDS,
            issuer=GOOGLE_ISSUERS,
            options={"require": list(REQUIRED_CLAIMS)},
        )
    except jwt.InvalidTokenError as error:
        raise InvalidGoogleToken from error
    if claims.get("email_verified") is not True:
        raise InvalidGoogleToken
    return claims


def find_identity_user(subject):
    identity = (
        ExternalIdentity.objects.select_related("user")
        .filter(provider=ExternalIdentity.GOOGLE, subject=subject)
        .first()
    )
    return identity.user if identity is not None else None


# Whoever registered this email before its owner could still log in with that password: an
# unverified account loses it, and its sessions, when the owner proves the email with Google.
def claim_unverified_account(user):
    user.is_email_verified = True
    user.set_unusable_password()
    user.save(update_fields=["is_email_verified", "password"])
    revoke_refresh_tokens(user)


def create_google_account(claims):
    if not settings.ALLOW_PUBLIC_REGISTRATION:
        raise PermissionDenied(PublicRegistrationEnabled.message)
    user = get_user_model().objects.create_user(
        email=claims["email"],
        password=None,
        first_name=claims.get("given_name", ""),
        last_name=claims.get("family_name", ""),
        is_email_verified=True,
    )
    emit_account_event(USER_REGISTERED, user)
    return user


# Google vouches for an address only on Gmail and on Workspace domains (the hd claim). Any
# other address was verified once, which is not enough to take over an existing account.
def is_google_authoritative(claims):
    return claims["email"].lower().endswith(GMAIL_DOMAIN) or bool(claims.get("hd"))


def adopt_existing_account(user, claims):
    if not is_google_authoritative(claims):
        raise AccountExists
    if not user.is_email_verified:
        claim_unverified_account(user)


@transaction.atomic
def link_google_account(claims):
    users = get_user_model().objects
    user = users.filter(email__iexact=claims["email"]).first()
    if user is None:
        user = create_google_account(claims)
    else:
        adopt_existing_account(user, claims)
    ExternalIdentity.objects.create(
        user=user, provider=ExternalIdentity.GOOGLE, subject=claims["sub"]
    )
    return user


def log_in_with_google(id_token):
    claims = verify_google_id_token(id_token)
    user = find_identity_user(claims["sub"]) or link_google_account(claims)
    if not user.is_active:
        raise InactiveAccount
    return user

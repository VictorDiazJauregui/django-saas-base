import json
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import override_settings

CLIENT_ID = "1234-test.apps.googleusercontent.com"
KEY_ID = "test-key"
GOOGLE_ISSUER = "https://accounts.google.com"
SUBJECT = "109876543210987654321"


def generate_private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


SIGNING_KEY = generate_private_key()
FOREIGN_KEY = generate_private_key()


def build_jwks(private_key=SIGNING_KEY, key_id=KEY_ID):
    public_jwk = json.loads(
        jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key())
    )
    return {"keys": [{**public_jwk, "kid": key_id, "alg": "RS256", "use": "sig"}]}


def build_claims(**overrides):
    now = int(time.time())
    claims = {
        "iss": GOOGLE_ISSUER,
        "aud": CLIENT_ID,
        "sub": SUBJECT,
        "email": "jane.doe@example.com",
        "email_verified": True,
        # A Workspace domain: Google vouches for the address.
        "hd": "example.com",
        "given_name": "Jane",
        "family_name": "Doe",
        "iat": now,
        "exp": now + 600,
    }
    return {**claims, **overrides}


def sign_id_token(private_key=SIGNING_KEY, **claim_overrides):
    return jwt.encode(
        build_claims(**claim_overrides),
        private_key,
        algorithm="RS256",
        headers={"kid": KEY_ID},
    )


def with_google_login(client_ids=(CLIENT_ID,)):
    return override_settings(
        GOOGLE_CLIENT_IDS=list(client_ids),
        GOOGLE_JWKS_URL="https://www.googleapis.com/oauth2/v3/certs",
    )

"""Shared ES256/JWKS test helpers (2026-08-13, local JWT verification).

Not a test module itself (no test_ prefix) -- imported by test_auth.py and
test_auth_jwt_verification.py so both exercise app/auth.py's real crypto
path (jwt.decode against a real EC keypair) instead of mocking it away.
"""
from __future__ import annotations

import json
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey

TEST_SUPABASE_URL = "https://pgwemjswxdlnshrfoggj.supabase.co"
TEST_ISSUER = f"{TEST_SUPABASE_URL}/auth/v1"
DEFAULT_KID = "test-kid-1"

_EC_ALG = jwt.algorithms.ECAlgorithm(jwt.algorithms.ECAlgorithm.SHA256)


def generate_keypair():
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key, private_key.public_key()


def jwk_for(public_key: EllipticCurvePublicKey, kid: str) -> dict:
    jwk = json.loads(_EC_ALG.to_jwk(public_key))
    jwk.update(kid=kid, alg="ES256", use="sig")
    return jwk


def jwks_body(*key_kid_pairs: tuple[EllipticCurvePublicKey, str]) -> dict:
    return {"keys": [jwk_for(pub, kid) for pub, kid in key_kid_pairs]}


def make_token(private_key, kid: str = DEFAULT_KID, **claim_overrides) -> str:
    now = int(time.time())
    payload = {
        "sub": "user-abc-123",
        "email": "advocate@example.com",
        "user_metadata": {"full_name": "Test Advocate"},
        "aud": "authenticated",
        "iss": TEST_ISSUER,
        "iat": now,
        "exp": now + 3600,
    }
    payload.update(claim_overrides)
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": kid})

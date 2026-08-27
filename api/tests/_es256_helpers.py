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


class _PermissiveQuery:
    """Ignores every filter/select arg and always returns the same canned
    row(s) -- see AlwaysAllowServiceClient below."""

    def __init__(self, data):
        self._data = data

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        return type("_Response", (), {"data": self._data})()


class AlwaysAllowServiceClient:
    """Permissive fake for app/auth.py::service_client(), for tests that
    exercise get_current_user() to verify JWT handling specifically (see
    test_auth.py / test_auth_jwt_verification.py) and have no reason to
    care about organization/account_security data -- both of which
    get_current_user() also checks as of the 27 Aug 2026 tenant-foundation
    work (account_security trial gate, then the organization membership/
    access gate). Every query returns exactly the row needed to pass both
    checks regardless of which user_id/organization_id is actually
    queried, so these tests keep testing only what they're named for.
    Do NOT reuse this for a test that asserts anything about organization
    or trial behavior -- use the real fakes in test_tenant_access_gate.py
    for that."""

    def table(self, name: str):
        if name == "account_security":
            return _PermissiveQuery([])  # no row -> "nothing to enforce yet"
        if name == "memberships":
            return _PermissiveQuery([{"organization_id": "always-allow-test-org"}])
        if name == "organizations":
            return _PermissiveQuery([{"access_enabled": True, "subscription_status": "active"}])
        return _PermissiveQuery([])

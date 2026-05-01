"""Unit tests for ES256 JWT sign/verify. Per ADR-0005 §2 and §3."""
import subprocess
import uuid

import pytest

from src.auth.jwt_utils import AuthError, create_access_token, decode_access_token

# Minimal ES256 key pair for tests only — NOT production keys
TEST_PRIVATE_KEY = """-----BEGIN EC PRIVATE KEY-----
MHcCAQEEINUKf38U94IQoOq/dEoYsxyLqYjnOXC3GAqMWobTnzxSoAoGCCqGSM49
AwEHoUQDQgAEnVbWIcXmEx/TyU/oblyoXtl8KrMqEapojcaWUflKuJ1QjIHjRCJg
Dy9GhmB7ejifIIb7Z6zowO2fgHcRUMGSYg==
-----END EC PRIVATE KEY-----"""

TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEnVbWIcXmEx/TyU/oblyoXtl8KrMq
EapojcaWUflKuJ1QjIHjRCJgDy9GhmB7ejifIIb7Z6zowO2fgHcRUMGSYg==
-----END PUBLIC KEY-----"""


def test_create_and_decode_access_token() -> None:
    user_id = uuid.uuid4()
    hc_id = uuid.uuid4()
    token = create_access_token(
        sub=str(user_id),
        role="hc",
        hc_id=str(hc_id),
        private_key=TEST_PRIVATE_KEY,
    )
    assert isinstance(token, str)
    claims = decode_access_token(token, public_key=TEST_PUBLIC_KEY)
    assert claims.sub == str(user_id)
    assert claims.role == "hc"
    assert claims.hc_id == str(hc_id)
    assert claims.iss == "https://api.parivarthan.com"


def test_expired_token_raises() -> None:
    token = create_access_token(
        sub=str(uuid.uuid4()), role="hc", hc_id=str(uuid.uuid4()),
        private_key=TEST_PRIVATE_KEY, ttl_seconds=-1,
    )
    with pytest.raises(AuthError, match="expired"):
        decode_access_token(token, public_key=TEST_PUBLIC_KEY)


def test_wrong_key_raises() -> None:
    subprocess.run(
        ["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", "/tmp/other_priv.pem"],
        capture_output=True, check=True,
    )
    subprocess.run(
        ["openssl", "ec", "-in", "/tmp/other_priv.pem", "-pubout", "-out", "/tmp/other_pub.pem"],
        capture_output=True, check=True,
    )
    with open("/tmp/other_pub.pem") as f:
        other_pub = f.read()
    token = create_access_token(
        sub=str(uuid.uuid4()), role="hc", hc_id=str(uuid.uuid4()),
        private_key=TEST_PRIVATE_KEY,
    )
    with pytest.raises(AuthError):
        decode_access_token(token, public_key=other_pub)


def test_client_role_hc_id_is_hc_not_self() -> None:
    client_id = uuid.uuid4()
    hc_id = uuid.uuid4()
    token = create_access_token(
        sub=str(client_id), role="client", hc_id=str(hc_id),
        private_key=TEST_PRIVATE_KEY,
    )
    claims = decode_access_token(token, public_key=TEST_PUBLIC_KEY)
    assert claims.role == "client"
    assert claims.hc_id == str(hc_id)
    assert claims.sub == str(client_id)

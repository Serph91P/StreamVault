"""Offline compatibility checks for security-patched auth dependencies."""

from importlib.metadata import version

import apprise
import jwt
from requests_oauthlib import OAuth2Session
import streamlink


def _release(package: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version(package).split(".")[:3])


def test_security_dependency_floors_are_patched():
    assert _release("multidict") >= (6, 9, 1)
    assert _release("PyJWT") >= (2, 15, 0)
    assert _release("urllib3") >= (2, 8, 0)


def test_patched_auth_dependencies_support_jwt_and_oauth_client_contracts():
    signing_key = "security-test-secret-key-32-bytes!"
    token = jwt.encode(
        {"sub": "security-test", "scp": ["system:read"]},
        signing_key,
        algorithm="HS256",
    )
    assert jwt.decode(token, signing_key, algorithms=["HS256"])["scp"] == [
        "system:read"
    ]

    session = OAuth2Session(
        client_id="streamvault-security-test",
        redirect_uri="https://localhost/oauth/callback",
        scope=["chat:read"],
    )
    authorization_url, state = session.authorization_url(
        "https://id.example.invalid/oauth2/authorize"
    )
    assert "client_id=streamvault-security-test" in authorization_url
    assert state

    assert apprise.Apprise() is not None
    assert streamlink

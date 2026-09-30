"""Offline compatibility checks for security-patched auth dependencies."""

import apprise
import jwt
from requests_oauthlib import OAuth2Session
import streamlink


def test_patched_auth_dependencies_support_jwt_and_oauth_client_contracts():
    token = jwt.encode(
        {"sub": "security-test", "scp": ["system:read"]},
        "security-test-secret",
        algorithm="HS256",
    )
    assert jwt.decode(token, "security-test-secret", algorithms=["HS256"])["scp"] == [
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

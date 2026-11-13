"""Verified TLS proxy connections must not load CA files on the event loop."""

import ssl
from threading import get_ident
from urllib.parse import urlsplit

import pytest

from app.services.http_client import ManagedHTTPClient, HTTPPolicy
from tests import test_webpush_delivery

receiver = test_webpush_delivery.receiver


@pytest.mark.asyncio
async def test_https_proxy_verifies_tls_with_worker_loaded_context(
    receiver, tmp_path, monkeypatch
):
    receiver["status"] = 200
    endpoint = urlsplit(receiver["subscription"]["endpoint"])
    loop_thread = get_ident()
    threads = []
    native_context = ssl.create_default_context

    def verified_context(*args, **kwargs):
        threads.append(get_ident())
        return native_context(cafile=str(tmp_path / "cert.pem"))

    monkeypatch.setattr(ssl, "create_default_context", verified_context)
    client = ManagedHTTPClient(HTTPPolicy(), proxy=f"https://{endpoint.netloc}")
    try:
        response = await client.request(
            "POST", "http://upstream.invalid/proxy-test", data={"probe": "fixture"}
        )
        assert response.status_code == 200
        assert threads and loop_thread not in threads
        assert receiver["requests"][0][0] == "http://upstream.invalid/proxy-test"
        assert receiver["requests"][0][2] == b"probe=fixture"
    finally:
        await client.close()

"""Real TLS transport and RFC8291 receiver, using only ephemeral test identities."""

import base64
from datetime import datetime, timedelta, timezone
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import logging
import os
import ssl
import threading
import time

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
import http_ece
import jwt
import pytest

from app.services.communication.webpush_service import (
    ModernWebPushService,
    WebPushException,
)


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


@pytest.fixture
def identity():
    key = ec.generate_private_key(ec.SECP256R1())
    raw = key.private_numbers().private_value.to_bytes(32, "big")
    return b64(raw), key.public_key()


@pytest.fixture
def receiver(tmp_path, monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), False)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    state = {"requests": [], "status": 201}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state["requests"].append(
                (
                    self.path,
                    dict(self.headers),
                    self.rfile.read(int(self.headers["Content-Length"])),
                )
            )
            self.send_response(state["status"])
            self.end_headers()
            self.wfile.write(b"untrusted endpoint-token-secret")

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("localhost", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    # Real verified TLS; trust only this fixture's self-signed certificate.
    from types import SimpleNamespace
    from importlib import import_module

    transport = import_module("app.services.communication.webpush_service")

    monkeypatch.setattr(
        transport,
        "http",
        SimpleNamespace(
            client=SimpleNamespace(
                HTTPSConnection=partial(
                    http.client.HTTPSConnection,
                    context=ssl.create_default_context(cafile=str(cert_path)),
                )
            )
        ),
    )
    ua = ec.generate_private_key(ec.SECP256R1())
    auth = os.urandom(16)
    state.update(
        ua=ua,
        auth=auth,
        subscription={
            "endpoint": f"https://localhost:{server.server_port}/push/endpoint-token-secret?token=private",
            "keys": {
                "p256dh": b64(
                    ua.public_key().public_bytes(
                        serialization.Encoding.X962,
                        serialization.PublicFormat.UncompressedPoint,
                    )
                ),
                "auth": b64(auth),
            },
        },
    )
    yield state
    server.shutdown()
    server.server_close()
    worker.join()


def test_real_tls_delivery_is_signed_encrypted_and_randomized(
    identity, receiver, caplog
):
    private, public = identity
    claims = {
        "sub": "mailto:push@example.com",
        "aud": "https://stale.example",
        "exp": 1,
    }
    service = ModernWebPushService(private, claims)
    payload = {
        "title": "Controlled StreamVault push",
        "body": "encrypted receipt",
        "data": {"url": "/notifications"},
    }
    caplog.set_level(logging.DEBUG, logger="streamvault")
    before = int(time.time())
    for _ in range(2):
        assert (
            service.send_notification(receiver["subscription"], payload, ttl=60) is True
        )
    assert claims == {
        "sub": "mailto:push@example.com",
        "aud": "https://stale.example",
        "exp": 1,
    }
    bodies = []
    for path, headers, body in receiver["requests"]:
        assert path == "/push/endpoint-token-secret?token=private"
        assert headers["Content-Encoding"] == "aes128gcm"
        assert headers["Content-Type"] == "application/octet-stream"
        assert headers["TTL"] == "60"
        token = headers["Authorization"].split("t=", 1)[1].split(",")[0]
        origin = receiver["subscription"]["endpoint"].split("/push/")[0]
        signed = jwt.decode(token, public, algorithms=["ES256"], audience=origin)
        assert signed["sub"] == "mailto:push@example.com"
        assert before < signed["exp"] <= int(time.time()) + 86400
        assert body[20] == 65  # RFC8188 keyid length, not an ad-hoc EC prefix
        assert len(body) <= 4096
        assert (
            json.loads(
                http_ece.decrypt(
                    body,
                    private_key=receiver["ua"],
                    auth_secret=receiver["auth"],
                    version="aes128gcm",
                )
            )
            == payload
        )
        bodies.append(body)
    assert bodies[0][:16] != bodies[1][:16]  # fresh salt
    assert bodies[0][21:86] != bodies[1][21:86]  # fresh ECDH key, not VAPID identity
    for secret in [
        "endpoint-token-secret",
        "token=private",
        *receiver["subscription"]["keys"].values(),
    ]:
        assert secret not in caplog.text


@pytest.mark.parametrize("status", [302, 400, 401, 403, 404, 410, 413, 429, 500, 503])
def test_http_failures_preserve_status_without_sensitive_logs(
    identity, receiver, caplog, status
):
    receiver["status"] = status
    caplog.set_level(logging.DEBUG, logger="streamvault")
    service = ModernWebPushService(identity[0], {"sub": "mailto:push@example.com"})
    with pytest.raises(WebPushException) as caught:
        service.send_notification(receiver["subscription"], {"title": "test"})
    assert caught.value.response.status == status
    assert "endpoint-token-secret" not in caplog.text
    assert "token=private" not in caplog.text


@pytest.fixture
def push_db(receiver):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import PushSubscription, GlobalSettings

    engine = create_engine("sqlite:///:memory:")
    PushSubscription.__table__.create(engine)
    GlobalSettings.__table__.create(engine)
    with Session(engine) as db:
        db.add(GlobalSettings(notifications_enabled=True, notify_online_global=True))
        sub = PushSubscription(
            endpoint=receiver["subscription"]["endpoint"],
            subscription_data=json.dumps(receiver["subscription"]),
            is_active=True,
        )
        db.add(sub)
        db.commit()
        yield db, sub
    engine.dispose()


@pytest.fixture
def enhanced(identity):
    from types import SimpleNamespace
    from app.services.communication.enhanced_push_service import EnhancedPushService

    service = EnhancedPushService()
    service.settings = SimpleNamespace(
        get_vapid_keys=lambda: {
            "private_key": identity[0],
            "public_key": "synthetic-present",
            "claims_sub": "mailto:push@example.com",
        }
    )
    return service


@pytest.mark.parametrize("status", [201, 403, 404, 410, 429, 503])
async def test_test_route_counts_and_persisted_expiry(
    identity, receiver, push_db, monkeypatch, caplog, status
):
    from importlib import import_module
    from types import SimpleNamespace

    route = import_module("app.routes.push")
    monkeypatch.setattr(
        route,
        "settings",
        SimpleNamespace(
            has_push_notifications_configured=True,
            VAPID_PRIVATE_KEY=identity[0],
            VAPID_CLAIMS_SUB="mailto:push@example.com",
        ),
    )
    receiver["status"] = status
    caplog.set_level(logging.DEBUG, logger="streamvault")
    db, sub = push_db
    result = await route.send_test_notification(db)
    assert result["sent_count"] == (1 if status == 201 else 0)
    assert result["failed_count"] == (0 if status == 201 else 1)
    db.expire_all()
    assert sub.is_active is (status != 410)
    assert "endpoint-token-secret" not in caplog.text


@pytest.mark.parametrize("status", [201, 403, 404, 410, 429, 503])
async def test_event_pipeline_only_deactivates_confirmed_expired(
    enhanced, receiver, push_db, monkeypatch, caplog, status
):
    from importlib import import_module
    from contextlib import nullcontext

    module = import_module("app.services.notifications.push_notification_service")
    db, sub = push_db
    monkeypatch.setattr(module, "SessionLocal", lambda: nullcontext(db))
    pipeline = module.PushNotificationService()
    pipeline.push_service = enhanced

    async def enabled(*args):
        return True

    monkeypatch.setattr(pipeline, "should_notify", enabled)
    receiver["status"] = status
    caplog.set_level(logging.DEBUG, logger="streamvault")
    await pipeline.send_push_notifications(
        "synthetic", "online", {"streamer_id": 1, "title": "test"}
    )
    assert len(receiver["requests"]) == 1
    db.expire_all()
    assert sub.is_active is (status != 410)
    assert (
        f"successful={1 if status == 201 else 0}, failed={0 if status == 201 else 1}"
        in caplog.text
    )
    assert "endpoint-token-secret" not in caplog.text


@pytest.mark.parametrize("status", [201, 410, 503])
async def test_notification_helper_uses_real_transport(
    enhanced, receiver, push_db, monkeypatch, status
):
    from app.utils import notification_utils
    from importlib import import_module

    module = import_module("app.services.communication.enhanced_push_service")
    monkeypatch.setattr(module, "enhanced_push_service", enhanced)
    monkeypatch.setattr(notification_utils, "_enhanced_push_service", None)
    receiver["status"] = status
    db, sub = push_db
    result = await notification_utils.send_push_notification(
        title="test", body="real send", db=db
    )
    assert len(receiver["requests"]) == 1
    assert result == {
        "sent": 1 if status == 201 else 0,
        "failed": 0 if status == 201 else 1,
        "skipped": 0,
    }
    db.expire_all()
    assert sub.is_active is (status != 410)


@pytest.mark.parametrize("damage", ["auth", "p256dh", "http", "oversize"])
def test_invalid_subscription_or_oversize_payload_never_posts(
    identity, receiver, damage, caplog
):
    sub = receiver["subscription"]
    payload = b"test"
    if damage in ("auth", "p256dh"):
        sub["keys"][damage] = "invalid-secret"
    elif damage == "http":
        sub["endpoint"] = sub["endpoint"].replace("https:", "http:")
    else:
        payload = b"x" * 3994  # 4096 minus 86 header minus 17 record overhead
    service = ModernWebPushService(identity[0], {"sub": "mailto:push@example.com"})
    assert service.send_notification(sub, payload) is False
    assert receiver["requests"] == []
    assert "invalid-secret" not in caplog.text


@pytest.mark.parametrize("operation", ["subscribe_to_push", "unsubscribe_from_push"])
async def test_subscription_database_failure_does_not_log_capabilities(
    operation, caplog
):
    from importlib import import_module
    from types import SimpleNamespace
    from fastapi import HTTPException

    def failed_query(*args):
        raise RuntimeError("SQL parameters: endpoint-token-secret auth-key-secret")

    db = SimpleNamespace(query=failed_query, rollback=lambda: None)
    route = import_module("app.routes.push")
    data = (
        {"subscription": {"endpoint": "https://example.com/endpoint-token-secret"}}
        if operation == "subscribe_to_push"
        else {"endpoint": "https://example.com/endpoint-token-secret"}
    )
    with pytest.raises(HTTPException):
        await getattr(route, operation)(data, db)
    assert "endpoint-token-secret" not in caplog.text
    assert "auth-key-secret" not in caplog.text


def test_initialization_error_never_logs_key(enhanced, monkeypatch, caplog):
    from importlib import import_module

    def invalid_key(**kwargs):
        raise ValueError("Invalid key: synthetic-key-secret")

    monkeypatch.setattr(
        import_module("app.services.communication.enhanced_push_service"),
        "ModernWebPushService",
        invalid_key,
    )
    assert enhanced.web_push_service is None
    assert "synthetic-key-secret" not in caplog.text

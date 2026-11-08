"""Real app/lifespan/PG/auth/HTTP coverage for the new catalog consumers."""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import jwt

from app.models import Session as LegacySession, User
from app.services.core.api_key_service import ApiKeyService
from app.services.core.auth_service import AuthService
from app.services.media.video_catalog_service import VideoCatalogService
from app.utils.token_store import ShareTokenModel
from test_fullstack_postgres_acceptance import fullstack_runtime as _fullstack_runtime

fullstack_runtime = _fullstack_runtime


def test_catalog_and_metadata_real_identity_boundaries(fullstack_runtime):
    runtime = fullstack_runtime
    client = runtime["client"]
    sessions = runtime["Session"]
    stream_id = runtime["stream_id"]
    login = client.post("/auth/login", json={"username": "acceptance-admin", "password": "acceptance-password"})
    assert login.status_code == 200
    client.cookies.delete("session")
    with sessions() as db:
        VideoCatalogService(db).reconcile_batch(limit=100)
        user = db.query(User).filter_by(username="acceptance-admin").one()
        legacy = asyncio.run(AuthService(db).create_session(user.id))
        _, api_key = ApiKeyService(db).create(user.id, "synthetic catalog acceptance")
        db.commit()
    paths = ["/api/videos/catalog", f"/api/videos/{stream_id}/metadata", f"/api/videos/{stream_id}/stream"]
    with httpx.Client(base_url=client.base_url, timeout=10, headers={"Accept": "application/json"}) as anonymous:
        for path in paths:
            assert anonymous.get(path).status_code == 401
        assert anonymous.head(paths[-1]).status_code == 401
        for path in paths:
            assert anonymous.get(path, headers={"X-API-Key": api_key}).status_code == 401
        assert anonymous.head(paths[-1], headers={"X-API-Key": api_key}).status_code == 401
    for path in paths:
        assert client.get(path).status_code == 200
    catalog = client.get(paths[0]).json()
    assert stream_id in [item["id"] for item in catalog["items"]]
    assert client.get(paths[1]).json()["id"] == stream_id
    assert client.get(paths[0], params={"page": 0}).status_code == 422
    assert client.get(paths[0], params={"sort": "untrusted"}).status_code == 422
    with httpx.Client(base_url=client.base_url, timeout=10, headers={"Accept": "application/json"}, cookies={"session": legacy}) as old_client:
        for path in paths:
            assert old_client.get(path).status_code == 200
        assert old_client.head(paths[-1]).status_code == 200
        with sessions() as db:
            row = db.query(LegacySession).filter_by(token=hashlib.sha256(legacy.encode()).hexdigest()).one()
            row.created_at = datetime.now(timezone.utc) - timedelta(days=365)
            db.commit()
        for path in paths:
            assert old_client.get(path).status_code == 401

    access = client.cookies.get("access_token")
    assert access
    payload = jwt.decode(access, options={"verify_signature": False})
    payload["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    expired = jwt.encode(payload, "ux09-local-acceptance-secret-at-least-32-characters", algorithm="HS256")
    with httpx.Client(base_url=client.base_url, timeout=10, headers={"Accept": "application/json"}, cookies={"access_token": expired}) as stale_client:
        for path in paths:
            assert stale_client.get(path).status_code == 401

    created = client.post(f"/api/videos/{stream_id}/share-token")
    assert created.status_code == 200
    token = parse_qs(urlparse(created.json()["share_url"]).query)["token"][0]
    with httpx.Client(base_url=client.base_url, timeout=10, headers={"Accept": "application/json"}) as public:
        # A share does not become catalog/metadata authorization.
        assert public.get(paths[0], params={"token": token}).status_code == 401
        assert public.get(paths[1], params={"token": token}).status_code == 401
        share = f"/api/videos/public/{stream_id}"
        response = public.get(share, params={"token": token}, headers={"range": "bytes=-5"})
        assert response.status_code == 206
        assert response.content == runtime["media_bytes"][-5:]
        assert public.head(share, params={"token": token}).status_code == 200
        with sessions() as db:
            db.query(ShareTokenModel).filter_by(token=token).one().expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        assert public.get(share, params={"token": token}).status_code == 401

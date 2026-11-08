"""A slow video must not pin middleware or nested dependency DB sessions."""

import asyncio
import importlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import dependencies
from app.config.settings import Settings
from app.database import Base
from app.models import Stream, Streamer, User
from app.routes import auth as auth_routes, videos
from app.services.core.api_key_service import ApiKeyService
from app.services.core.auth_service import AuthService
from app.utils import token_store


def test_authenticated_slow_media_releases_all_db_scopes_before_body(tmp_path, monkeypatch):
    middleware = importlib.import_module("app.middleware.auth")
    settings_module = importlib.import_module("app.config.settings")
    root = tmp_path / "recordings"
    root.mkdir()
    media = root / "synthetic.ts"
    payload = b"synthetic local media" * 10000
    media.write_bytes(payload)
    config = Settings(RECORDING_DIRECTORY=str(root), AUTH_JWT_SECRET="synthetic-pool-one-secret-at-least-32-characters", _env_file=None)
    engine = create_engine(f"sqlite:///{tmp_path / 'pool.db'}", pool_size=1, max_overflow=0, pool_timeout=0.1)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    for module in (dependencies, middleware, token_store, videos):
        monkeypatch.setattr(module, "SessionLocal", sessions)
    monkeypatch.setattr(settings_module, "get_settings", lambda: config)
    with sessions() as db:
        user = User(username="synthetic-pool", password=secrets.token_urlsafe(32), is_admin=True, is_active=True)
        channel = Streamer(username="synthetic-pool", twitch_id="synthetic-pool")
        db.add_all([user, channel])
        db.flush()
        stream = Stream(streamer_id=channel.id, title="Synthetic pool test", started_at=datetime.now(timezone.utc), recording_path=str(media))
        db.add(stream)
        db.commit()
        stream_id = stream.id
        auth = AuthService(db, settings=config)
        access = auth.create_access_token(user)
        legacy = asyncio.run(auth.create_session(user.id))
        _, key = ApiKeyService(db).create(user.id, "synthetic pool key")
    token_store.store_share_token("synthetic-share", stream_id, 60)
    application = FastAPI()
    application.include_router(videos.router)
    application.include_router(auth_routes.router, prefix="/auth")
    application.add_middleware(middleware.AuthMiddleware)
    held = []
    queries = []

    class ObserveBody:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            successful = False

            async def observe(message):
                nonlocal successful
                if message["type"] == "http.response.start":
                    successful = message["status"] in (200, 206)
                if successful and message["type"] == "http.response.body":
                    held.append(engine.pool.checkedout())
                    if held[-1] == 0:
                        # A different request's real SQL can use this one-connection pool.
                        with engine.connect() as db:
                            queries.append(db.scalar(text("SELECT 1")))
                    await asyncio.sleep(0.002)
                await send(message)

            await self.app(scope, receive, observe)

    application.add_middleware(ObserveBody)
    try:
        with TestClient(application) as client:
            setup = client.get("/auth/setup", headers={"Accept": "application/json"})
            assert setup.status_code == 200
            assert setup.json() == {"setup_required": False, "welcome_completed": False}
            assert engine.pool.checkedout() == 0
            for cookie in ({"access_token": access}, {"session": legacy}):
                client.cookies.clear()
                client.cookies.update(cookie)
                response = client.get(f"/api/videos/{stream_id}/stream", headers={"Accept": "application/json"})
                assert response.status_code == 200
                assert response.content == payload
            client.cookies.clear()
            share = client.get(f"/api/videos/public/{stream_id}", params={"token": "synthetic-share"})
            assert share.status_code == 200
            assert share.content == payload
            with sessions() as db:
                db.query(token_store.ShareTokenModel).filter_by(token="synthetic-share").one().expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                db.commit()
            assert client.get(f"/api/videos/public/{stream_id}", params={"token": "synthetic-share"}).status_code == 401
            assert client.get(f"/api/videos/{stream_id}/stream", headers={"Accept": "application/json", "X-API-Key": key}).status_code == 401
        assert held and set(held) == {0}
        assert queries == [1] * len(held)
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()

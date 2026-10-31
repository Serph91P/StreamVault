"""Opt-in live-provider fixture: production push/PWA routers, disposable identity/SQLite.

From repository root, after a REAL frontend build:
    PYTHONPATH=. uv run python tests/manual/webpush_provider.py
Then run tests/manual/webpush_provider.cjs with Firefox/Playwright installed.
This fixture deliberately does not exercise application authentication/bootstrap.
"""

import base64
import os
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import uvicorn
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def main():
    key = ec.generate_private_key(ec.SECP256R1())

    def b64(value):
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

    private_key = b64(key.private_numbers().private_value.to_bytes(32, "big"))
    public_key = b64(
        key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    )
    with TemporaryDirectory(prefix="webpush-probe-") as scratch:
        # Set synthetic configuration before importing any application services.
        os.environ.update(
            DATABASE_URL="sqlite:///:memory:",
            TWITCH_APP_ID="synthetic",
            TWITCH_APP_SECRET="synthetic",
            BASE_URL="http://127.0.0.1:4187",
            LOGS_BASE_DIR=scratch,
            LOG_DIR=scratch,
            RECORDING_DIRECTORY=scratch,
            VAPID_PRIVATE_KEY=private_key,
            VAPID_PUBLIC_KEY=public_key,
            VAPID_CLAIMS_SUB="mailto:push@example.com",
        )
        from app.database import get_db
        from app.frontend import pwa_router
        from app.models import GlobalSettings, PushSubscription
        from app.routes import push

        push.settings = SimpleNamespace(
            has_push_notifications_configured=True,
            VAPID_PRIVATE_KEY=private_key,
            VAPID_PUBLIC_KEY=public_key,
            VAPID_CLAIMS_SUB="mailto:push@example.com",
        )
        engine = create_engine(
            "sqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        PushSubscription.__table__.create(engine)
        GlobalSettings.__table__.create(engine)
        with Session(engine) as db:
            db.add(GlobalSettings(notifications_enabled=True))
            db.commit()

        def isolated_db():
            with Session(engine) as db:
                yield db

        app = FastAPI()
        app.dependency_overrides[get_db] = isolated_db

        @app.get("/probe.html")
        def probe():
            return HTMLResponse(
                "<html><title>Native Web Push</title><body>Controlled probe</body></html>"
            )

        app.include_router(push.router)
        app.include_router(pwa_router)
        app.mount("/assets", StaticFiles(directory="app/frontend/dist/assets"))
        app.mount("/pwa", StaticFiles(directory="app/frontend/dist"))
        try:
            uvicorn.run(
                app, host="127.0.0.1", port=4187, access_log=False, log_level="warning"
            )
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()

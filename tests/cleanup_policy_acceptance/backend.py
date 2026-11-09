"""Isolated product factory/routers, synthetic SQLite, no background lifespan."""

import importlib
import json
import os
from datetime import datetime, timedelta

from fastapi import Depends
from pydantic import SecretStr

from app.config.settings import settings
from app.database import Base, SessionLocal, database_lifecycle
from app.dependencies import require_interactive_identity
from app.models import (
    GlobalSettings,
    RecordingSettings,
    Streamer,
    StreamerRecordingSettings,
    SystemState,
    User,
)
from app.services.core.auth_service import AuthService

settings.auth_jwt_secret = SecretStr(os.environ["ACCEPTANCE_JWT"])
settings.USE_SECURE_COOKIES = False
Base.metadata.create_all(database_lifecycle.sync_engine)
with SessionLocal() as db:
    db.add(
        User(
            username="policy-admin",
            is_admin=True,
            is_active=True,
            password=AuthService(db).hash_password(os.environ["ACCEPTANCE_PASSWORD"]),
        )
    )
    db.add(SystemState(id=1, welcome_completed=True))
    db.add(GlobalSettings(supported_codecs="h264,h265"))
    db.add(
        RecordingSettings(
            enabled=False,
            output_directory=os.environ["RECORDING_DIRECTORY"],
            filename_template="{streamer}",
            default_quality="best",
            use_chapters=True,
        )
    )
    db.add(
        Streamer(
            id=947,
            twitch_id="synthetic-947",
            username="synthetic-policy",
            is_live=False,
            auto_record=False,
        )
    )
    db.add(
        StreamerRecordingSettings(
            streamer_id=947, enabled=False, use_global_cleanup_policy=True
        )
    )
    db.commit()

# Settings also reads version information before revealing its panels. Seed the
# existing update cache so an unrelated external GitHub lookup cannot stall this
# isolated persistence acceptance (all auth/settings/DB routes remain real).
version_routes = importlib.import_module("app.routes.version")
version_routes._update_check_cache.update(
    data={
        "update_available": False,
        "latest_version": None,
        "latest_version_url": None,
        "update_check_error": None,
        "release_channel": "prerelease",
    },
    expires_at=datetime.utcnow() + timedelta(minutes=5),
)

app = importlib.import_module("app.main").create_app(settings=settings)


@app.get("/_acceptance/state", dependencies=[Depends(require_interactive_identity)])
def state():
    # Separate DB session; never echo a browser request or frontend state.
    with SessionLocal() as db:
        global_settings = db.query(RecordingSettings).one()
        channel = db.query(StreamerRecordingSettings).filter_by(streamer_id=947).one()
        return {
            "global": json.loads(global_settings.cleanup_policy)
            if global_settings.cleanup_policy
            else None,
            "channel": json.loads(channel.cleanup_policy)
            if channel.cleanup_policy
            else None,
            "inherits": channel.use_global_cleanup_policy,
        }


# Test-only readback must precede the production SPA catch-all.
app.router.routes.insert(0, app.router.routes.pop())

"""Real app/router/service/repository; only provider I/O is synthetic.

Runs only in the runner's disposable /scratch SQLite container without lifespan.
Never use against an existing database. Auth uses a generated synthetic admin.
"""

import asyncio
import importlib
import os
import socket

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
from app.services.streamers.twitch_integration_service import TwitchIntegrationService
from app.services.unified_image_service import unified_image_service

assert os.environ["DATABASE_URL"] == "sqlite:////scratch/acceptance.sqlite"
settings.auth_jwt_secret = SecretStr(os.environ["ACCEPTANCE_JWT"])
settings.USE_SECURE_COOKIES = False
Base.metadata.create_all(database_lifecycle.sync_engine)
with SessionLocal() as db:
    db.add(
        User(
            username="onboarding-admin",
            is_admin=True,
            is_active=True,
            password=AuthService(db).hash_password(os.environ["ACCEPTANCE_PASSWORD"]),
        )
    )
    db.add(SystemState(id=1, welcome_completed=False))
    db.add(GlobalSettings(supported_codecs="h264"))
    db.add(
        RecordingSettings(
            enabled=False,
            output_directory="/scratch/recordings",
            filename_template="{streamer}",
            default_quality="480p",
            use_chapters=False,
        )
    )
    db.commit()

provider_calls = []
release = asyncio.Event()


async def users(self, usernames):
    provider_calls.extend(usernames)
    name = usernames[0]
    if name == "providerfailure":
        raise RuntimeError("Synthetic provider unavailable")
    if name != "synthetic995":
        return []
    await release.wait()
    return [
        {
            "id": "995",
            "login": name,
            "display_name": name,
            "profile_image_url": "",
            "offline_image_url": "",
            "description": "Synthetic onboarding channel",
        }
    ]


async def streams(self, twitch_id):
    return None


async def subscribe(self, twitch_id):
    assert twitch_id == "995"


async def image(*args, **kwargs):
    return None


# Preserve get_user_data, add_streamer, repository commit and every route.
TwitchIntegrationService.get_users_by_login = users
TwitchIntegrationService.get_stream_info = streams
TwitchIntegrationService.subscribe_to_events = subscribe
unified_image_service.download_profile_image = image
app = importlib.import_module("app.main").create_app(settings=settings)


@app.post("/_acceptance/release", dependencies=[Depends(require_interactive_identity)])
async def allow_provider():
    release.set()
    return {"released": True}


@app.get("/_acceptance/state", dependencies=[Depends(require_interactive_identity)])
def state():
    # New DB session after the actual repository commit, never a request echo.
    with SessionLocal() as db:
        global_settings = db.query(GlobalSettings).one()
        recording = db.query(RecordingSettings).one()
        channels = db.query(Streamer).all()
        channel_settings = db.query(StreamerRecordingSettings).all()
        return {
            "channels": [{"id": row.id, "username": row.username} for row in channels],
            "global_codec": global_settings.supported_codecs,
            "recording_quality": recording.default_quality,
            "recording_enabled": recording.enabled,
            "channel_settings": [
                {
                    "quality": row.quality,
                    "custom_filename": row.custom_filename,
                    "use_global_cleanup_policy": row.use_global_cleanup_policy,
                }
                for row in channel_settings
            ],
            "welcome_completed": db.query(SystemState).one().welcome_completed,
            "provider_calls": provider_calls,
        }


app.router.routes.sort(
    key=lambda route: not getattr(route, "path", "").startswith("/_acceptance/")
)


def no_outbound(*args, **kwargs):
    raise RuntimeError("Outbound socket forbidden in synthetic onboarding acceptance")


socket.socket.connect = no_outbound
socket.socket.connect_ex = no_outbound

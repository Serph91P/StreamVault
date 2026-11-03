"""Real product composition with disposable SQLite/media and test-only controls.

No API fixtures, production lifespan, external identity or application data.
Controls invoke real producers/trackers; business requests use product routers.
"""

from __future__ import annotations

import asyncio
import importlib
from datetime import datetime, timedelta, timezone
import logging
import json
import os
from pathlib import Path
import subprocess

from fastapi import Depends
from pydantic import SecretStr

from app.config.settings import settings
from app.database import Base, database_lifecycle, SessionLocal
from app.dependencies import require_interactive_identity, websocket_manager
from app.models import (
    GlobalSettings,
    NotificationSettings,
    RecordingSettings,
    Stream,
    Streamer,
    StreamerRecordingSettings,
    SystemState,
    User,
)
from app.services.core.auth_service import AuthService
from app.services.background_queue_service import background_queue_service
from app.services.queues.task_progress_tracker import (
    QueueTask,
    TaskPriority,
    TaskStatus,
)

settings.auth_jwt_secret = SecretStr(os.environ["ACCEPTANCE_JWT"])
settings.USE_SECURE_COOKIES = False
Base.metadata.create_all(database_lifecycle.sync_engine)
media = Path("/scratch/recordings/acceptance.mp4")
media.parent.mkdir(parents=True, exist_ok=True)
if not media.exists():
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=15",
            "-t",
            "12",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(media),
        ],
        check=True,
        timeout=30,
    )
with SessionLocal() as db:
    if not db.query(User).first():
        db.add(
            User(
                username="realtime-admin",
                is_admin=True,
                is_active=True,
                password=AuthService(db).hash_password(
                    os.environ["ACCEPTANCE_PASSWORD"]
                ),
            )
        )
        db.add(SystemState(id=1, welcome_completed=True))
        db.add(GlobalSettings(supported_codecs="h264,h265"))
        db.add(
            RecordingSettings(
                enabled=True,
                output_directory=str(media.parent),
                filename_template="{streamer}",
                filename_preset="default",
                default_quality="best",
                use_chapters=True,
            )
        )
        db.add(
            Streamer(
                id=933,
                twitch_id="synthetic-933",
                username="synthetic-channel",
                is_live=False,
                auto_record=False,
            )
        )
        db.add(
            NotificationSettings(
                streamer_id=933,
                notify_online=True,
                notify_offline=True,
                notify_update=True,
            )
        )
        db.add(
            StreamerRecordingSettings(
                streamer_id=933, enabled=False, use_global_cleanup_policy=True
            )
        )
        db.commit()

# The production factory registers the actual routers, middleware and SPA.
app = importlib.import_module("app.main").create_app(settings=settings)
logging.getLogger("streamvault").setLevel(logging.CRITICAL)
tracker = background_queue_service.queue_manager.progress_tracker
tracker.websocket_manager = websocket_manager


def seed_task():
    tracker.active_tasks.clear()
    tracker.completed_tasks.clear()
    tracker.add_task(
        QueueTask(
            id="acceptance-933",
            task_type="acceptance",
            priority=TaskPriority.NORMAL,
            payload={"streamer_name": "Synthetic acceptance", "stream_id": 933},
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
    )


seed_task()
if Path("/scratch/restarted").exists():
    asyncio.run(
        websocket_manager.send_notification(
            {
                "type": "channel.update",
                "data": {
                    "test_id": "after-process-restart",
                    "message": "Synthetic event after actual process restart",
                },
            }
        )
    )


@app.post("/_acceptance/seed", dependencies=[Depends(require_interactive_identity)])
async def seed():
    seed_task()
    with SessionLocal() as db:
        for id in (933, 934):
            if not db.get(Stream, id):
                copy = media.with_name(f"acceptance-{id}.mp4")
                copy.write_bytes(media.read_bytes())
                db.add(
                    Stream(
                        id=id,
                        streamer_id=933,
                        twitch_stream_id=f"synthetic-{id}",
                        title=f"Synthetic recording {id}",
                        started_at=datetime.now(timezone.utc) - timedelta(seconds=12),
                        ended_at=datetime.now(timezone.utc),
                        recording_path=str(copy),
                    )
                )
        db.commit()
    return {"seeded": True}


@app.get("/_acceptance/state", dependencies=[Depends(require_interactive_identity)])
def state():
    # A separate real session, not a copy of request/response or UI state.
    with SessionLocal() as db:
        global_settings = db.query(GlobalSettings).first()
        channel = db.query(StreamerRecordingSettings).filter_by(streamer_id=933).one()
        notifications = db.query(NotificationSettings).filter_by(streamer_id=933).one()
        return {
            "global_codec": global_settings.supported_codecs,
            "channel_codec": channel.supported_codecs,
            "channel_enabled": channel.enabled,
            "use_global_cleanup_policy": channel.use_global_cleanup_policy,
            "cleanup_policy": json.loads(channel.cleanup_policy)
            if channel.cleanup_policy
            else None,
            "notify_online": notifications.notify_online,
            "streams": [row.id for row in db.query(Stream).all()],
            "pid": os.getpid(),
        }


@app.post(
    "/_acceptance/task/{action}", dependencies=[Depends(require_interactive_identity)]
)
async def task(action: str):
    if action == "run":
        tracker.update_task_status("acceptance-933", TaskStatus.RUNNING)
    elif action == "progress":
        tracker.update_task_progress("acceptance-933", 45)
    elif action == "complete":
        tracker.update_task_progress("acceptance-933", 100)
        tracker.update_task_status("acceptance-933", TaskStatus.COMPLETED)
    if tracker.background_tasks:
        await asyncio.gather(*list(tracker.background_tasks))
    await tracker.send_queue_statistics()
    return {"action": action}


@app.post(
    "/_acceptance/disconnect", dependencies=[Depends(require_interactive_identity)]
)
async def disconnect():
    await websocket_manager.close_all()
    await websocket_manager.send_notification(
        {
            "type": "channel.update",
            "data": {
                "test_id": "during-disconnect",
                "message": "Synthetic missed notification replay",
            },
        }
    )
    return {"disconnected": True}


@app.post("/_acceptance/restart", dependencies=[Depends(require_interactive_identity)])
async def restart():
    Path("/scratch/restart-requested").touch()
    return {"restart_requested": True, "pid": os.getpid()}


# Keep test-only controls ahead of the production SPA catch-all.
app.router.routes.sort(
    key=lambda route: not getattr(route, "path", "").startswith("/_acceptance/")
)

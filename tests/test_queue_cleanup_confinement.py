"""Verify the corrected cleanup contracts using only synthetic catalog and media."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models import Recording, Stream, Streamer, StreamMetadata
from tests.test_recording_capabilities import headers, stack as stack

URL = "/api/background-queue/tasks/enqueue"


@pytest.fixture
def media(stack):
    _, database, settings, _, _ = stack
    root = Path(settings.RECORDING_DIRECTORY)
    own = root / "synthetic"
    other = root / "other"
    own.mkdir(parents=True)
    other.mkdir()
    final = own / "episode.mp4"
    source = own / "episode.ts"
    final.write_bytes(b"f" * (1024 * 1024))
    source.write_bytes(b"synthetic source")
    protected = other / source.name
    protected.write_bytes(b"other channel")
    now = datetime.now(timezone.utc)
    with database.sync_session_factory() as db:
        db.add(Streamer(id=2, username="other", twitch_id="other"))
        db.flush()
        db.add_all(
            [
                Stream(id=1, streamer_id=1, recording_path=str(final), ended_at=now),
                Stream(
                    id=2, streamer_id=2, recording_path=str(protected), ended_at=now
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                Recording(
                    id=1,
                    stream_id=1,
                    start_time=now,
                    status="completed",
                    path=str(final),
                ),
                Recording(
                    id=2,
                    stream_id=2,
                    start_time=now,
                    status="completed",
                    path=str(protected),
                ),
            ]
        )
        db.commit()
    return final, source, protected


async def drain(app, task_id):
    manager = app.state.background_queue_manager
    queue = app.state.background_queue_service
    await manager.initialize()
    try:
        async with asyncio.timeout(8):
            while True:
                task = queue.queue_manager.get_task(task_id)
                if task and task.status.value in {"completed", "failed"}:
                    return task.status.value
                await asyncio.sleep(0.02)
    finally:
        await manager.shutdown()
        await queue.stop()


@pytest.mark.parametrize("mode", ["post_processing", "artifacts"])
def test_manual_cleanup_removes_only_owned_source(stack, media, mode):
    app, _, _, client, _ = stack
    final, source, protected = media
    segments = final.with_name("episode_segments")
    segments.mkdir()
    (segments / "episode_part001.ts").write_bytes(b"owned segment")
    original = final.read_bytes()
    result = client.post(
        URL,
        params={"task_type": "cleanup", "max_retries": 0},
        headers=headers(stack, "jwt", "admin"),
        json={"stream_id": 1, "recording_id": 1, "mode": mode},
    )
    assert result.status_code == 200, result.text
    task_id = result.json()["task_id"]

    assert asyncio.run(drain(app, task_id)) == "completed"
    assert not source.exists()
    assert not segments.exists()
    assert final.read_bytes() == original
    assert protected.read_bytes() == b"other channel"


@pytest.mark.parametrize("url", ["/api/streams/1", "/api/streamers/1/streams/1"])
def test_explicit_delete_removes_final_before_catalog_is_discarded(stack, media, url):
    _, database, _, client, _ = stack
    final, source, protected = media
    response = client.delete(url, headers=headers(stack, "jwt", "writer"))
    assert response.status_code == 200, response.text
    assert response.json()["deleted_files_count"] == 2
    assert not final.exists() and not source.exists()
    assert protected.read_bytes() == b"other channel"
    with database.sync_session_factory() as db:
        assert db.get(Stream, 1) is None
        assert db.get(Stream, 2) is not None


@pytest.mark.parametrize(
    "state,expected", [("anonymous", 401), ("reader", 403), ("writer", 403)]
)
def test_cleanup_admission_requires_admin(stack, media, state, expected):
    app, _, _, client, _ = stack
    response = client.post(
        URL,
        params={"task_type": "cleanup"},
        headers=headers(stack, "jwt", state),
        json={"stream_id": 1},
    )
    assert response.status_code == expected
    assert not app.state.background_queue_service.get_active_tasks()
    assert media[1].read_bytes() == b"synthetic source"


@pytest.mark.parametrize(
    "task,body",
    [
        ("unregistered", {"stream_id": 1}),
        ("file_cleanup", {"stream_id": 1}),
        ("cleanup", {}),
        ("cleanup", {"stream_id": 999}),
        ("cleanup", {"stream_id": 1, "recording_id": 2}),
        ("cleanup", {"stream_id": "1"}),
        ("cleanup", {"stream_id": 1, "files_to_remove": []}),
        ("cleanup", {"stream_id": 1, "cleanup_paths": "legacy"}),
    ],
)
def test_manual_schema_and_catalog_rejections_never_enqueue(stack, media, task, body):
    app, _, _, client, _ = stack
    response = client.post(
        URL,
        params={"task_type": task},
        headers=headers(stack, "jwt", "admin"),
        json=body,
    )
    assert response.status_code == 422
    assert not app.state.background_queue_service.get_active_tasks()
    assert all(path.is_file() for path in media)


@pytest.mark.parametrize("mode", ["post_processing", "artifacts"])
@pytest.mark.parametrize(
    "mutation", ["output-missing", "output-small", "parent-replaced", "shared"]
)
def test_worker_preserves_sources_when_admitted_provenance_is_no_longer_safe(
    stack, media, mode, mutation
):
    app, database, _, client, _ = stack
    final, source, protected = media
    if mutation == "output-missing":
        final.unlink()
    elif mutation == "output-small":
        final.write_bytes(b"too small")
    response = client.post(
        URL,
        params={"task_type": "cleanup", "max_retries": 0},
        headers=headers(stack, "jwt", "admin"),
        json={"stream_id": 1, "recording_id": 1, "mode": mode},
    )
    assert response.status_code == 200, response.text
    if mutation == "parent-replaced":
        old_parent = source.parent.rename(source.parent.with_name("kept"))
        source.parent.symlink_to(protected.parent, target_is_directory=True)
        source = old_parent / source.name
    elif mutation == "shared":
        with database.sync_session_factory() as db:
            db.add(StreamMetadata(stream_id=2, nfo_path=str(source)))
            db.commit()
    assert asyncio.run(drain(app, response.json()["task_id"])) == "failed"
    assert source.read_bytes() == b"synthetic source"
    assert protected.read_bytes() == b"other channel"


@pytest.mark.parametrize(
    "kind", ["outside", "traversal", "sibling", "root", "symlink", "shared"]
)
def test_catalog_cannot_authorize_unconfined_or_shared_media(stack, media, kind):
    app, database, settings, client, tmp = stack
    final, source, protected = media
    root = Path(settings.RECORDING_DIRECTORY)
    sibling = root.with_name(root.name + "-neighbor")
    sibling.mkdir()
    link = root / "linked"
    link.symlink_to(sibling, target_is_directory=True)
    external = sibling / "external.mp4"
    external.write_bytes(b"synthetic sentinel")
    candidate = {
        "outside": tmp / "external.mp4",
        "traversal": root / "synthetic" / ".." / "episode.mp4",
        "sibling": external,
        "root": root,
        "symlink": link / external.name,
        "shared": final,
    }[kind]
    with database.sync_session_factory() as db:
        if kind == "shared":
            db.get(Stream, 2).recording_path = str(final)
        else:
            db.get(Stream, 1).recording_path = str(candidate)
            db.get(Recording, 1).path = str(candidate)
        db.commit()
    response = client.post(
        URL,
        params={"task_type": "cleanup"},
        headers=headers(stack, "key", "admin"),
        json={"stream_id": 1, "recording_id": 1},
    )
    assert response.status_code == 422
    assert not app.state.background_queue_service.get_active_tasks()
    assert all(path.is_file() for path in (final, source, protected))
    assert external.read_bytes() == b"synthetic sentinel"


@pytest.mark.parametrize("mode_key", ["files_to_remove", "cleanup_paths"])
def test_internal_legacy_selection_cannot_delete_other_media(stack, media, mode_key):
    app, _, _, _, _ = stack
    final, source, protected = media
    unrelated = source.with_name("unrelated.ts")
    unrelated.write_bytes(b"unowned")
    handler = app.state.background_queue_manager.task_handlers
    for target in (unrelated, protected, final):
        with pytest.raises(ValueError, match="does not belong"):
            asyncio.run(
                handler.handle_cleanup(
                    {
                        "stream_id": 1,
                        "recording_id": 1,
                        mode_key: [str(source), str(target)],
                    }
                )
            )
    assert unrelated.read_bytes() == b"unowned"
    assert source.read_bytes() == b"synthetic source"
    assert protected.read_bytes() == b"other channel"
    assert final.stat().st_size == 1024 * 1024

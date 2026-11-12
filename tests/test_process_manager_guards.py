"""ProcessManager defensive guards degrade without a child, lease, or loop I/O.

Value: protects=absent process/segment/token inputs return False/None rather than a
manufactured success or a silent exception;
fails_when=an empty registry is reported as running, a missing segment is reported as
captured, or a token-service fault leaks;
why_new=native child/queue/liveness tables cover real processes, not these no-op guards;
seam=none; no_claim=provider capture, media admission or process termination.
"""

import asyncio

import pytest

from app.services.recording.process_manager import ProcessManager


def bare_manager(**attrs):
    manager = ProcessManager.__new__(ProcessManager)
    manager.lock = asyncio.Lock()
    manager.active_processes = {}
    manager.long_stream_processes = {}
    manager._is_shutting_down = False
    manager.post_processing_callback = None
    for key, value in attrs.items():
        setattr(manager, key, value)
    return manager


@pytest.mark.asyncio
async def test_process_manager_missing_identity_guards_return_false(
    tmp_path, monkeypatch
):
    manager = bare_manager()
    assert (
        ProcessManager._segment_has_recording_data(str(tmp_path / "absent.ts")) is False
    )
    empty = tmp_path / "empty.ts"
    empty.write_bytes(b"")
    assert ProcessManager._segment_has_recording_data(str(empty)) is False
    populated = tmp_path / "populated.ts"
    populated.write_bytes(b"segment bytes")
    assert ProcessManager._segment_has_recording_data(str(populated)) is True

    def raising_stat(self, *args, **kwargs):
        raise OSError("synthetic segment stat denial")

    monkeypatch.setattr("pathlib.Path.stat", raising_stat)
    assert ProcessManager._segment_has_recording_data(str(populated)) is True

    assert manager.get_active_process_count() == 0
    assert manager.is_shutting_down() is False
    assert await manager.is_capture_running(7) is False


@pytest.mark.asyncio
async def test_process_manager_token_resolution_and_callback_guards():
    manager = bare_manager()

    class ExplodingTokenService:
        async def resolve_recording_token(self):
            raise RuntimeError("synthetic token-service fault")

    manager.twitch_token_service = ExplodingTokenService()
    assert await manager._resolve_recording_token() is None

    def callback(recording_id, path):
        raise AssertionError("callback must not be invoked by assignment")

    manager.set_post_processing_callback(callback)
    assert manager.post_processing_callback is callback

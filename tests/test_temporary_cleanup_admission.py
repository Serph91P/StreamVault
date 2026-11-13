"""Real file/SQLite guard interleaving for #938, not an event-loop mock."""

import asyncio
import threading
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services.system import temporary_cleanup_service as cleanup
from app.services.twitch_upstream_coordinator import TwitchUpstreamCoordinator


@pytest.mark.asyncio
async def test_confirmed_unlink_serializes_with_new_capture_reservation(
    tmp_path, monkeypatch
):
    root = tmp_path / "recordings"
    root.mkdir()
    target = root / "old.tmp"
    target.write_bytes(b"expired unowned scratch")
    old = time.time() - 48 * 3600
    import os

    os.utime(target, (old, old))
    engine = create_engine(f"sqlite:///{tmp_path / 'guard.sqlite'}")
    with engine.begin() as connection:
        Base.metadata.create_all(connection)
    factory = sessionmaker(bind=engine)
    entered, release, attempted, acquired = (threading.Event() for _ in range(4))
    original_unlink = cleanup.os.unlink
    reservation = None
    operation = None
    try:
        preview = await cleanup.cleanup_temporary_files(
            root, factory, cleanup.TemporaryCleanupRequest()
        )
        request = cleanup.TemporaryCleanupRequest.model_validate(
            {"dry_run": False, "confirmed": True, "candidates": preview["candidates"]}
        )

        def paused_unlink(path, *args, **kwargs):
            if str(path) == "old.tmp" and "dir_fd" in kwargs:
                entered.set()
                assert release.wait(3), "test must release the guarded unlink"
            return original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(cleanup.os, "unlink", paused_unlink)
        coordinator = TwitchUpstreamCoordinator(factory, monotonic_clock=time.monotonic)
        begin = coordinator._begin_guarded_transaction

        def observed_begin(db):
            attempted.set()
            begin(db)
            acquired.set()

        monkeypatch.setattr(coordinator, "_begin_guarded_transaction", observed_begin)
        operation = asyncio.create_task(
            cleanup.cleanup_temporary_files(root, factory, request)
        )
        assert await asyncio.to_thread(entered.wait, 2)
        reservation = asyncio.create_task(
            coordinator.reserve(
                channel_key="938-race", auth_key=None, purpose="RECORDING"
            )
        )
        assert await asyncio.to_thread(attempted.wait, 2)
        assert not await asyncio.to_thread(acquired.wait, 0.15)
        release.set()
        result = await operation
        assert result["files_removed"] == 1
        assert not target.exists()
        await reservation
        assert acquired.is_set()
        # Only after admission may the new owner create its output at that name.
        target.write_bytes(b"newly admitted owner")
        assert target.read_bytes() == b"newly admitted owner"
    finally:
        release.set()
        for task in (operation, reservation):
            if task is not None:
                await asyncio.gather(task, return_exceptions=True)
        engine.dispose()

"""Default live output is private/ephemeral; explicit roots remain caller-owned."""

import asyncio
from pathlib import Path
import stat
import tempfile
from threading import get_ident, Event
from types import SimpleNamespace

import pytest

from app.services import live_streaming_service as module


@pytest.mark.asyncio
async def test_default_root_is_lazy_private_unique_and_only_owner_stop_removes_it(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    threads = []
    original = tempfile.mkdtemp

    def create(*args, **kwargs):
        threads.append(get_ident())
        return original(*args, **kwargs)

    monkeypatch.setattr(tempfile, "mkdtemp", create)
    loop_thread = get_ident()
    first, second = module.LiveStreamingService(), module.LiveStreamingService()
    assert threads == [] and list(tmp_path.iterdir()) == []
    try:
        await asyncio.gather(first.start(), second.start())
        roots = first._output_root, second._output_root
        assert roots[0] != roots[1]
        for index, root in enumerate(roots):
            assert root is not None
            assert root.is_dir() and root.parent == tmp_path
            assert not root.is_symlink() and stat.S_IMODE(root.stat().st_mode) == 0o700
            (root / "playlist.m3u8").write_text(f"fixture-{index}")
        assert len(threads) == 2 and loop_thread not in threads
        await first.stop()
        assert not roots[0].exists()
        assert (roots[1] / "playlist.m3u8").read_text() == "fixture-1"
        await first.start()
        assert first._output_root not in roots and first._output_root.is_dir()
    finally:
        await first.stop()
        await second.stop()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_explicit_live_root_and_untracked_files_remain_caller_owned(tmp_path):
    root = tmp_path / "caller-owned"
    root.mkdir()
    marker = root / "existing-recording.ts"
    marker.write_bytes(b"caller data")
    service = module.LiveStreamingService(output_root=root)
    await service.start()
    await service.stop()
    await service.stop()
    assert service._output_root == root
    assert marker.read_bytes() == b"caller data"


@pytest.mark.asyncio
async def test_actual_live_directory_creation_ignores_planted_predictable_root(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    target = tmp_path / "other-owner"
    target.mkdir()
    (target / "keep").write_text("untouched")
    planted = tmp_path / "streamvault-live"
    planted.symlink_to(target, target_is_directory=True)

    # Translate ONLY the old hardcoded root into our sandbox; never touch shared /tmp.
    def sandbox_path(value):
        return planted if str(value) == "/tmp/streamvault-live" else Path(value)

    monkeypatch.setattr(module, "Path", sandbox_path)

    class Coordinator:
        async def reserve(self, **values):
            return SimpleNamespace(
                live_session_id=values["live_session_id"], generation=1
            )

        async def release(self, **values):
            return True

    service = module.LiveStreamingService(coordinator=Coordinator())
    observed = []

    async def command(*args, **kwargs):
        return ["local-fixture"]

    async def spawn(*args, **kwargs):
        directory = Path(args[-1]).parent
        assert directory.is_dir()
        observed.append(directory.resolve())
        raise RuntimeError("controlled child boundary")

    service._build_streamlink_command = command
    monkeypatch.setattr(module.shutil, "which", lambda name: name)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    try:
        with pytest.raises(RuntimeError, match="controlled child boundary"):
            await service.start_stream("channel", user_id="1")
        assert len(observed) == 1
        assert not observed[0].is_relative_to(target), (
            "Real mkdir followed planted root symlink"
        )
        assert (target / "keep").read_text() == "untouched"
        assert planted.is_symlink()
    finally:
        await service.stop()
    assert list(target.iterdir()) == [target / "keep"]


@pytest.mark.asyncio
async def test_shutdown_during_reservation_cannot_recreate_released_default_root(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    entered, release = asyncio.Event(), asyncio.Event()
    spawned, released = [], []

    class Coordinator:
        async def reserve(self, **values):
            entered.set()
            await release.wait()
            return SimpleNamespace(
                live_session_id=values["live_session_id"], generation=1
            )

        async def release(self, **values):
            released.append(values)
            return True

    service = module.LiveStreamingService(coordinator=Coordinator())

    async def command(*args, **kwargs):
        return ["local-fixture"]

    async def spawn(*args, **kwargs):
        spawned.append(args)
        raise RuntimeError("unexpected late child boundary")

    service._build_streamlink_command = command
    monkeypatch.setattr(module.shutil, "which", lambda name: name)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    operation = asyncio.create_task(service.start_stream("channel", user_id="1"))
    try:
        assert await asyncio.wait_for(entered.wait(), 5)
        root = service._output_root
        assert root is not None
        assert root.is_dir()
        await service.stop()
        assert not root.exists()
        release.set()
        with pytest.raises(RuntimeError, match="stopped"):
            await operation
        assert not root.exists() and spawned == []
        assert len(released) == 1 and released[0]["reason"] == "live_start_failed"
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
        await service.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["create", "cleanup"])
async def test_private_root_cancellation_retains_worker_ownership(
    tmp_path, monkeypatch, phase
):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    entered, release = Event(), Event()
    service = module.LiveStreamingService()
    roots = []
    if phase == "create":
        original = module.TemporaryDirectory

        def create(*args, **kwargs):
            resource = original(*args, **kwargs)
            roots.append(Path(resource.name))
            entered.set()
            assert release.wait(10)
            return resource

        monkeypatch.setattr(module, "TemporaryDirectory", create)
        operation = asyncio.create_task(service.start())
    else:
        await service.start()
        assert service._temporary_output is not None
        roots.append(service._output_root)
        original = service._temporary_output.cleanup

        def cleanup():
            entered.set()
            assert release.wait(10)
            original()

        monkeypatch.setattr(service._temporary_output, "cleanup", cleanup)
        operation = asyncio.create_task(service.stop())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        for _ in range(2):
            operation.cancel()
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(operation), 0.05)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await operation
        if phase == "create":
            assert service._output_root == roots[0] and roots[0].is_dir()
        else:
            assert service._output_root is None and not roots[0].exists()
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
        await service.stop()
    assert roots and all(not path.exists() for path in roots)

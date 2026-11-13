"""Real concat media, source preservation and child lifetime, without a provider."""

import asyncio
import os
from threading import Event as ThreadEvent, get_ident

import pytest

from app.services.recording.unified_recovery_service import UnifiedRecoveryService


async def media(directory):
    directory.mkdir()
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=64x64:r=10",
        "-t",
        "3",
        "-c:v",
        "libx264",
        "-g",
        "10",
        "-f",
        "segment",
        "-segment_time",
        "1",
        str(directory / "segment_%03d.ts"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, error = await process.communicate()
    assert process.returncode == 0, error.decode()
    return {path.name: path.read_bytes() for path in directory.iterdir()}


@pytest.mark.asyncio
@pytest.mark.parametrize("directory_name", ["segments", "seg'ments"])
async def test_recovery_concat_is_off_loop_and_preserves_existing_manifest(
    tmp_path, monkeypatch, directory_name
):
    segments = tmp_path / directory_name
    originals = await media(segments)
    manifest = segments / "concat_list.txt"
    manifest.write_bytes(b"existing user file")
    output = tmp_path / "joined.ts"
    probes = []
    loop = get_ident()
    real_stat = os.stat

    def stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(str(tmp_path)):
            probes.append(get_ident())
        return real_stat(path, *args, **kwargs)

    with monkeypatch.context() as watched:
        watched.setattr(os, "stat", stat)
        result = await UnifiedRecoveryService()._concatenate_segments_util(
            segments, output
        )
    assert result == output
    assert probes and loop not in probes
    assert manifest.read_bytes() == b"existing user file"
    assert {path.name for path in segments.iterdir()} == set(originals) | {
        "concat_list.txt"
    }
    for name, data in originals.items():
        assert (segments / name).read_bytes() == data
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(output),
        "-f",
        "null",
        "-",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, error = await process.communicate()
    assert process.returncode == 0, error.decode()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancellations", ["once", "worker", "creation"])
async def test_recovery_concat_cancellation_reaps_real_child_and_keeps_sources(
    tmp_path, monkeypatch, cancellations
):
    segments = tmp_path / "segments"
    originals = await media(segments)
    output = tmp_path / "joined.ts"
    children = []
    started = asyncio.Event()
    spawn = asyncio.create_subprocess_exec
    service = UnifiedRecoveryService()
    cleanup_entered = ThreadEvent()
    cleanup_release = ThreadEvent()
    creation_release = asyncio.Event()
    real_cleanup = service._cleanup_concat_paths

    def held_cleanup(paths):
        cleanup_entered.set()
        assert cleanup_release.wait(5)
        real_cleanup(paths)

    async def slow_spawn(*command, **kwargs):
        command = list(command)
        command.insert(command.index("-i"), "-re")
        process = await spawn(*command, **kwargs)
        children.append(process)
        started.set()
        if cancellations == "creation":
            await creation_release.wait()
        return process

    operation = None
    try:
        with monkeypatch.context() as watched:
            watched.setattr(asyncio, "create_subprocess_exec", slow_spawn)
            if cancellations == "worker":
                watched.setattr(service, "_cleanup_concat_paths", held_cleanup)
            operation = asyncio.create_task(
                service._concatenate_segments_util(segments, output)
            )
            await asyncio.wait_for(started.wait(), 5)
            operation.cancel()
            if cancellations == "worker":
                assert await asyncio.to_thread(cleanup_entered.wait, 5)
                operation.cancel()
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                assert not operation.done()
                cleanup_release.set()
            elif cancellations == "creation":
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                operation.cancel()
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                assert not operation.done()
                creation_release.set()
            with pytest.raises(asyncio.CancelledError):
                await operation
        assert children[0].returncode is not None
        assert not output.exists()
        assert {path.name for path in segments.iterdir()} == set(originals)
        for name, data in originals.items():
            assert (segments / name).read_bytes() == data
    finally:
        creation_release.set()
        cleanup_release.set()
        if operation is not None and not operation.done():
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
        for child in children:
            if child.returncode is None:
                child.kill()
                await child.communicate()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["empty", "corrupt", "existing", "appearing"])
async def test_recovery_concat_failure_keeps_sources_and_peer_outputs(
    tmp_path, monkeypatch, case
):
    segments = tmp_path / "segments"
    if case in {"existing", "appearing"}:
        originals = await media(segments)
    else:
        segments.mkdir()
        originals = (
            {}
            if case == "empty"
            else {"invalid.ts": b"not valid transport stream bytes"}
        )
        for name, data in originals.items():
            (segments / name).write_bytes(data)
    output = tmp_path / "joined.ts"
    if case == "existing":
        output.write_bytes(b"peer data")
    spawn = asyncio.create_subprocess_exec

    async def racing_spawn(*command, **kwargs):
        process = await spawn(*command, **kwargs)
        output.write_bytes(b"peer data")
        return process

    with monkeypatch.context() as watched:
        if case == "appearing":
            watched.setattr(asyncio, "create_subprocess_exec", racing_spawn)
        assert (
            await UnifiedRecoveryService()._concatenate_segments_util(segments, output)
            is None
        )
    assert {path.name for path in segments.iterdir()} == set(originals)
    assert not list(tmp_path.glob(".recovery-*"))
    for name, data in originals.items():
        assert (segments / name).read_bytes() == data
    if case in {"existing", "appearing"}:
        assert output.read_bytes() == b"peer data"
    else:
        assert not output.exists()

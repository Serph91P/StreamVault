"""Real segment publication/cleanup effects under collisions and filesystem faults.

Protects the finalizer's worker boundary, original bytes, and truthful output-path
publication. Removing collision resolution, swallowing a failed move as success,
or returning before cleanup drains breaks these tests. OS fault injection is only
at the failing operation; no fake FFmpeg/provider/queue success is claimed.
"""

import asyncio
from pathlib import Path
from threading import Event, get_ident

import pytest

from tests.test_process_manager_guards import bare_manager


@pytest.mark.asyncio
async def test_move_collision_same_path_and_failed_move_preserve_originals(
    tmp_path, monkeypatch
):
    manager = bare_manager()
    directory = tmp_path / "segments"
    directory.mkdir()
    source = directory / "final.ts"
    source.write_bytes(b"captured source")
    existing = tmp_path / "final.ts"
    existing.write_bytes(b"peer bytes")
    copy = tmp_path / "final_copy1.ts"
    copy.write_bytes(b"prior copy")
    info = {"segment_dir": str(directory), "base_output_path": str(source)}
    await manager._move_concatenated_file_to_parent(info)
    published = tmp_path / "final_copy2.ts"
    assert info["final_output_path"] == str(published)
    assert published.read_bytes() == b"captured source"
    assert not source.exists()
    assert existing.read_bytes() == b"peer bytes" and copy.read_bytes() == b"prior copy"

    same = {"segment_dir": str(directory), "base_output_path": str(published)}
    await manager._move_concatenated_file_to_parent(same)
    assert same["final_output_path"] == str(published)
    source.write_bytes(b"retry source")
    failed = {"segment_dir": str(directory), "base_output_path": str(source)}
    threads = []

    def denied_move(*_args, **_kwargs):
        threads.append(get_ident())
        raise PermissionError("synthetic move denial")

    with monkeypatch.context() as fault:
        fault.setattr("shutil.move", denied_move)
        await manager._move_concatenated_file_to_parent(failed)
    assert "final_output_path" not in failed
    assert source.read_bytes() == b"retry source"
    assert threads and get_ident() not in threads
    await manager._move_concatenated_file_to_parent(failed)
    assert Path(failed["final_output_path"]).read_bytes() == b"retry source"
    assert existing.read_bytes() == b"peer bytes"


@pytest.mark.asyncio
async def test_cleanup_failed_unlink_retains_source_and_retries_off_loop(
    tmp_path, monkeypatch
):
    manager = bare_manager()
    directory = tmp_path / "segments"
    directory.mkdir()
    source = directory / "part.ts"
    source.write_bytes(b"captured bytes")
    manifest = directory / "concat_list.txt"
    manifest.write_text("manifest")
    info = {"segment_dir": str(directory), "total_segments": [{"path": str(source)}]}
    unlink = Path.unlink
    threads = []

    def fail_source(path, *args, **kwargs):
        threads.append(get_ident())
        if path == source:
            raise PermissionError("synthetic unlink denial")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as fault:
        fault.setattr(Path, "unlink", fail_source)
        await manager._cleanup_segments(info)
    assert source.read_bytes() == b"captured bytes"
    assert not manifest.exists() and directory.exists()
    assert threads and get_ident() not in threads
    await manager._cleanup_segments(info)
    assert not directory.exists()


@pytest.mark.asyncio
async def test_cleanup_cancellation_drains_real_worker_before_return(
    tmp_path, monkeypatch
):
    manager = bare_manager()
    directory = tmp_path / "segments"
    directory.mkdir()
    source = directory / "part.ts"
    source.write_bytes(b"owned bytes")
    info = {"segment_dir": str(directory), "total_segments": [{"path": str(source)}]}
    entered, release = Event(), Event()
    unlink = Path.unlink

    def held_unlink(path, *args, **kwargs):
        if path == source:
            entered.set()
            assert release.wait(5)
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as fault:
        fault.setattr(Path, "unlink", held_unlink)
        task = asyncio.create_task(manager._cleanup_segments(info))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done() and source.exists()
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
    assert not source.exists() and not directory.exists()


@pytest.mark.asyncio
async def test_empty_missing_and_invalid_finalization_never_admit_work(tmp_path):
    manager = bare_manager()
    directory = tmp_path / "segments"
    directory.mkdir()
    empty = directory / "empty_part000.ts"
    empty.touch()
    for folder in (directory, tmp_path / "missing"):
        info = {
            "stream_id": 7,
            "monitor_task": None,
            "segment_dir": str(folder),
            "total_segments": [{"path": str(tmp_path / "missing.ts")}],
            "base_output_path": str(tmp_path / "final.ts"),
        }
        await manager._finalize_segmented_recording(info)
        assert "final_output_path" not in info
        assert not (folder / "concat_list.txt").exists()
    assert empty.read_bytes() == b""
    assert not (tmp_path / "final.ts").exists()

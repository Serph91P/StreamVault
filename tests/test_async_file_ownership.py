"""Cancellation must not return ownership while a file mutation still runs."""

import asyncio
from pathlib import Path
import shutil
from threading import Event, get_ident

import pytest

from app.utils import async_file


@pytest.mark.asyncio
async def test_file_helpers_keep_values_paths_errors_and_real_mutation_effects(
    tmp_path,
):
    directory = tmp_path / "nested"
    await async_file.mkdir(str(directory))
    await async_file.mkdir(directory)
    child = directory / "child"
    await async_file.makedirs(child)
    source = directory / "original.bin"
    source.write_bytes(b"literal bytes")
    assert await async_file.exists(source)
    assert await async_file.isfile(str(source))
    assert await async_file.isdir(directory)
    assert await async_file.getsize(source) == 13
    assert await async_file.path_exists(source)
    assert await async_file.path_is_file(source)
    assert await async_file.path_is_dir(directory)
    assert (await async_file.path_stat(source)).st_size == 13
    assert await async_file.basename(source) == "original.bin"
    assert await async_file.dirname(source) == str(directory)
    assert await async_file.splitext(source) == (str(directory / "original"), ".bin")
    assert await async_file.join(directory, "original.bin") == str(source)
    assert await async_file.abspath(source) == str(source)
    assert await async_file.normpath(directory / "child/../original.bin") == str(source)
    assert sorted(await async_file.listdir(directory)) == ["child", "original.bin"]
    assert await async_file.glob_list(str(directory / "*.bin")) == [str(source)]
    assert sorted(await async_file.walk(directory)) == [
        (str(directory), ["child"], ["original.bin"]),
        (str(child), [], []),
    ]
    copied = child / "copy.bin"
    await async_file.copy2(source, copied)
    assert copied.read_bytes() == b"literal bytes"
    moved = child / "moved.bin"
    await async_file.move(copied, moved)
    assert moved.read_bytes() == b"literal bytes" and not copied.exists()
    await async_file.remove(moved)
    await async_file.unlink(source)
    source.write_bytes(b"retry")
    await async_file.unlink(str(source))
    assert not source.exists()
    await async_file.rmdir(child)
    assert not child.exists()
    for helper in (async_file.getsize, async_file.path_stat, async_file.remove):
        with pytest.raises(FileNotFoundError):
            await helper(source)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["copy2", "move", "path_unlink", "path_mkdir"])
async def test_cancelled_file_mutation_drains_its_worker_before_return(
    operation, tmp_path, monkeypatch
):
    source = tmp_path / "source.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"literal preserved source")
    loop = asyncio.get_running_loop()
    entered, finished = asyncio.Event(), asyncio.Event()
    release = Event()
    threads = []
    if operation in ("copy2", "move"):
        native = getattr(shutil, operation)
        owner, name = shutil, operation
        arguments = (source, target)
    else:
        name = "unlink" if operation == "path_unlink" else "mkdir"
        native = getattr(Path, name)
        owner = Path
        arguments = (source if name == "unlink" else target,)

    def held(*args, **kwargs):
        threads.append(get_ident())
        loop.call_soon_threadsafe(entered.set)
        try:
            assert release.wait(5), "fixture worker was never released"
            return native(*args, **kwargs)
        finally:
            loop.call_soon_threadsafe(finished.set)

    monkeypatch.setattr(owner, name, held)
    task = asyncio.create_task(getattr(async_file, operation)(*arguments))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        for _ in range(5):
            await asyncio.sleep(0)
        assert not task.done(), "file worker outlived its cancelled owner"
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done(), "repeated cancellation abandoned the file worker"
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()
        assert threads and get_ident() not in threads
        if operation in ("copy2", "move"):
            assert target.read_bytes() == b"literal preserved source"
            assert source.exists() is (operation == "copy2")
        elif operation == "path_unlink":
            assert not source.exists()
        else:
            assert target.is_dir()
            assert source.read_bytes() == b"literal preserved source"
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.wait_for(finished.wait(), 2)

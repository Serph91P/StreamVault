"""Static Streamlink configuration has no credential/provider work or loop I/O."""

import asyncio
import builtins
from pathlib import Path

from threading import Event, get_ident

import pytest

from app.models import GlobalSettings
from app.services.system.streamlink_config_service import StreamlinkConfigService
from tests import test_proxy_http_ownership

proxy_applications = test_proxy_http_ownership.proxy_applications
image_applications = test_proxy_http_ownership.image_applications


@pytest.mark.asyncio
async def test_static_config_uses_closed_owned_catalogue_and_worker_files(
    proxy_applications, tmp_path, monkeypatch
):
    _, databases, _, queries = proxy_applications
    with databases[0].sync_session_factory() as session:
        session.query(GlobalSettings).one().supported_codecs = "h265,h264"
        session.commit()
    directory = tmp_path / "own-config"
    service = StreamlinkConfigService(
        config_dir=directory, session_factory=databases[0].sync_session_factory
    )
    assert not directory.exists()
    native_generate = service.generate_twitch_config
    writers = []

    def generate(**kwargs):
        writers.append(get_ident())
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
        return native_generate(**kwargs)

    monkeypatch.setattr(service, "generate_twitch_config", generate)
    queries.clear()
    assert await service.update_config_from_settings()
    assert queries and all(thread != get_ident() for thread, _ in queries)
    assert writers and get_ident() not in writers
    assert (
        "twitch-supported-codecs=h265,h264\n" in service.twitch_config_path.read_text()
    )
    assert (
        "twitch-supported-codecs=h264\n"
        in service.twitch_anonymous_config_path.read_text()
    )
    assert "twitch-api-header=" not in service.twitch_config_path.read_text()


@pytest.mark.asyncio
async def test_static_config_cancellation_drains_real_file_publication(
    proxy_applications, tmp_path, monkeypatch
):
    _, databases, _, _ = proxy_applications
    directory = tmp_path / "cancelled-config"
    service = StreamlinkConfigService(
        config_dir=directory, session_factory=databases[0].sync_session_factory
    )
    entered, release = Event(), Event()
    native_generate = service.generate_twitch_config

    def generate(**kwargs):
        entered.set()
        assert release.wait(5)
        return native_generate(**kwargs)

    monkeypatch.setattr(service, "generate_twitch_config", generate)
    task = asyncio.create_task(service.update_config_from_settings())
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel()
        for _ in range(10):
            await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert service.twitch_config_path.is_file()
    assert service.twitch_anonymous_config_path.is_file()
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)


@pytest.mark.parametrize("error", [PermissionError, OSError, RuntimeError])
def test_static_config_open_failure_preserves_existing_bytes(
    tmp_path, monkeypatch, error
):
    service = StreamlinkConfigService(config_dir=tmp_path)
    service.twitch_config_path.write_bytes(b"prior static configuration")
    native_open = builtins.open

    def fail_open(file, *args, **kwargs):
        if Path(file) == service.twitch_config_path:
            raise error("fixture write failure")
        return native_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fail_open)
    assert service.generate_twitch_config() is False
    assert service.twitch_config_path.read_bytes() == b"prior static configuration"


@pytest.mark.asyncio
async def test_static_config_database_failure_does_not_publish(tmp_path):
    def unavailable():
        raise OSError("fixture unavailable catalogue")

    service = StreamlinkConfigService(config_dir=tmp_path, session_factory=unavailable)
    service.twitch_config_path.write_bytes(b"prior static configuration")
    assert await service.regenerate_config() is False
    assert service.twitch_config_path.read_bytes() == b"prior static configuration"
    assert not service.twitch_anonymous_config_path.exists()

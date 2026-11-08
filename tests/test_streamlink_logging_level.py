"""Capture defaults must not enable permanent Streamlink debug output."""

import pytest

from app.services.system.streamlink_config_service import StreamlinkConfigService
from app.utils.streamlink_utils import (
    get_streamlink_clip_command,
    get_streamlink_vod_command,
)


@pytest.mark.parametrize("level,expected", [("INFO", "info"), ("DEBUG", "debug")])
def test_streamlink_log_level_follows_explicit_app_debug(
    monkeypatch, tmp_path, level, expected
):
    monkeypatch.setenv("LOG_LEVEL", level)
    service = object.__new__(StreamlinkConfigService)
    service.config_dir = tmp_path
    service.twitch_config_path = tmp_path / "config.twitch"
    service.twitch_anonymous_config_path = tmp_path / "config.twitch-anonymous"
    assert service.generate_twitch_config()
    for path in (service.twitch_config_path, service.twitch_anonymous_config_path):
        assert f"loglevel={expected}\n" in path.read_text()
    for command in (
        get_streamlink_vod_command("123", "best", str(tmp_path / "vod.ts")),
        get_streamlink_clip_command(
            "https://clips.twitch.tv/example", "best", str(tmp_path / "clip.ts")
        ),
    ):
        assert command[command.index("--loglevel") + 1] == expected

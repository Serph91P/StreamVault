import importlib.util
from pathlib import Path


_module_path = (
    Path(__file__).resolve().parents[1]
    / "app/services/system/streamlink_config_service.py"
)
_spec = importlib.util.spec_from_file_location(
    "streamlink_config_service_under_test", _module_path
)
assert _spec and _spec.loader
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
StreamlinkConfigService = _module.StreamlinkConfigService


def test_generate_twitch_config_uses_deterministic_streamlink_8_4_options(tmp_path):
    # Given: differing HTTP and HTTPS proxies and a writable config path
    service = StreamlinkConfigService.__new__(StreamlinkConfigService)
    service.config_dir = tmp_path
    service.twitch_config_path = tmp_path / "config.twitch"

    # When: the Twitch plugin config is generated
    assert service.generate_twitch_config(
        http_proxy="http://http-proxy.example:8080",
        https_proxy="http://https-proxy.example:8443",
    )

    # Then: Streamlink 8.4.0 receives one deterministic proxy and stability budget
    config_lines = service.twitch_config_path.read_text(encoding="utf-8").splitlines()
    assert config_lines.count("http-proxy=http://http-proxy.example:8080") == 1
    assert not any(line.startswith("https-proxy=") for line in config_lines)
    assert "hls-live-edge=3" in config_lines
    assert "retry-streams=10" in config_lines
    assert "retry-max=2" in config_lines
    assert "stream-segment-threads=5" in config_lines

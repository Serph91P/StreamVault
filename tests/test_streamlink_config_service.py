import importlib.util
import socket
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest


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


@pytest.fixture
def local_hls_server(monkeypatch):
    requests = Counter()
    playlist = b"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:1
#EXT-X-MEDIA-SEQUENCE:0
#EXTINF:1.0,
segment.ts
#EXT-X-ENDLIST
"""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests[self.path] += 1
            if self.path == "/playlist.m3u8":
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(playlist)))
                self.end_headers()
                self.wfile.write(playlist)
                return

            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, _format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    original_connect = socket.socket.connect

    def loopback_connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            host = address[0]
            if not ip_address(host).is_loopback:
                raise OSError(f"External network access blocked: {host}")
        return original_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", loopback_connect)
    host, port = server.server_address
    try:
        yield SimpleNamespace(
            requests=requests,
            url=lambda path: f"http://{host}:{port}{path}",
        )
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)


def _generated_config_options(service):
    assert service.generate_twitch_config()
    return dict(
        line.split("=", 1)
        for line in service.twitch_config_path.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )


def test_generate_twitch_config_redacts_proxy_credentials_from_log(tmp_path, caplog):
    service = StreamlinkConfigService.__new__(StreamlinkConfigService)
    service.config_dir = tmp_path
    service.twitch_config_path = tmp_path / "config.twitch"
    proxy_url = "http://user:password@proxy.example.com:8080"

    with caplog.at_level("INFO", logger="streamvault"):
        assert service.generate_twitch_config(http_proxy=proxy_url)

    assert "user" not in caplog.text
    assert "password" not in caplog.text
    assert "proxy.example.com:8080" in caplog.text


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


def test_missing_stream_resolution_stays_within_three_http_attempts(
    tmp_path, monkeypatch, local_hls_server
):
    streamlink = pytest.importorskip("streamlink")
    streamlink_cli = pytest.importorskip("streamlink_cli.main")
    assert streamlink.__version__ == "8.4.0"

    service = StreamlinkConfigService.__new__(StreamlinkConfigService)
    service.config_dir = tmp_path
    service.twitch_config_path = tmp_path / "config.twitch"
    options = _generated_config_options(service)

    session = streamlink.Streamlink({"no-plugin-cache": True})
    session.http.trust_env = False
    url = local_hls_server.url("/missing.m3u8")
    _, plugin_class, resolved_url = session.resolve_url(url)
    plugin = plugin_class(session, resolved_url)
    monkeypatch.setattr(
        streamlink_cli,
        "args",
        SimpleNamespace(
            stream_types=["hls", "http", "*"], stream_sorting_excludes=None
        ),
    )
    monkeypatch.setattr(streamlink_cli, "sleep", lambda _interval: None)

    streams = streamlink_cli.fetch_streams_with_retry(
        plugin,
        interval=0,
        count=int(options["retry-max"]),
    )

    assert not streams
    assert local_hls_server.requests["/missing.m3u8"] == 3


def test_retriable_hls_segment_stays_within_six_http_attempts(
    monkeypatch, local_hls_server
):
    streamlink = pytest.importorskip("streamlink")
    assert streamlink.__version__ == "8.4.0"
    from app.utils.streamlink_utils import get_streamlink_command
    from streamlink.stream.hls import HLSStream

    command = get_streamlink_command(
        streamer_name="test_streamer",
        quality="best",
        output_path="/tmp/test.ts",
        proxy_settings={"http": "http://proxy.example.com:8080"},
    )
    attempts_index = command.index("--stream-segment-attempts")
    retry_attempts = int(command[attempts_index + 1])

    session = streamlink.Streamlink(
        {
            "no-plugin-cache": True,
            "stream-segment-attempts": retry_attempts,
            "stream-segment-threads": 1,
        }
    )
    session.http.trust_env = False
    monkeypatch.setattr("streamlink.session.http.time.sleep", lambda _delay: None)
    stream = HLSStream(session, local_hls_server.url("/playlist.m3u8"))

    reader = stream.open()
    try:
        assert reader.read(8192) == b""
    finally:
        reader.close()

    assert local_hls_server.requests["/segment.ts"] == 6

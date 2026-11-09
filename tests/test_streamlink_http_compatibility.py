"""#834: locked Streamlink must prepare Twitch URLs before any network I/O."""

import pytest
import requests
from streamlink.session.http import HTTPSession


@pytest.mark.parametrize(
    ("method", "url", "expected"),
    [
        ("POST", "https://gql.twitch.tv/gql", "https://gql.twitch.tv/gql"),
        (
            "GET",
            "https://example.test/a%2fb?key=value%2fpart",
            "https://example.test/a%2fb?key=value%2fpart",
        ),
        ("GET", "https://example.test/a b", "https://example.test/a%20b"),
    ],
)
def test_native_request_preparation_without_http_send(method, url, expected):
    # This is the real pre-send path that failed with Streamlink 8.6.0/urllib3 2.8.
    with HTTPSession() as session:
        prepared = session.prepare_request(requests.Request(method, url))
    assert prepared.method == method
    assert prepared.url == expected

"""
Test Streamlink command formatting to ensure arguments are properly escaped.

This test validates the fix for the OAuth token parsing issue where Streamlink
was receiving the token as separate arguments instead of a single argument.

ISSUE: Streamlink was receiving:
  --twitch-api-header Authorization=OAuth token
  (3 separate arguments, parsed as tuple)

FIX: Now sends:
  --twitch-api-header=Authorization=OAuth token
  (1 single argument, properly parsed)
"""

import pytest
from app.utils.streamlink_utils import get_streamlink_command


def test_oauth_token_format():
    """Test that OAuth token is passed as single argument with ="""
    cmd = get_streamlink_command(
        streamer_name="test_streamer",
        quality="best",
        output_path="/tmp/test.ts",
        oauth_token="test_token_123"
    )
    
    # Find the OAuth argument
    oauth_arg = None
    for arg in cmd:
        if arg.startswith("--twitch-api-header="):
            oauth_arg = arg
            break
    
    # Verify format
    assert oauth_arg is not None, "OAuth argument not found in command"
    assert oauth_arg == "--twitch-api-header=Authorization=OAuth test_token_123"
    
    # Verify it's NOT split into separate arguments
    assert "--twitch-api-header" not in cmd or any("=" in arg for arg in cmd if "--twitch-api-header" in arg), \
        "OAuth token must use = format to avoid shell parsing issues"


def test_codec_format():
    """Test that codecs are passed as single argument with ="""
    cmd = get_streamlink_command(
        streamer_name="test_streamer",
        quality="best",
        output_path="/tmp/test.ts",
        supported_codecs="h264,h265,av1"
    )
    
    # Find the codec argument
    codec_arg = None
    for arg in cmd:
        if arg.startswith("--twitch-supported-codecs="):
            codec_arg = arg
            break
    
    # Verify format
    assert codec_arg is not None, "Codec argument not found in command"
    assert codec_arg == "--twitch-supported-codecs=h264,h265,av1"


def test_proxy_format():
    """Test that proxy URLs are passed as single argument with ="""
    cmd = get_streamlink_command(
        streamer_name="test_streamer",
        quality="best",
        output_path="/tmp/test.ts",
        proxy_settings={
            "http": "http://user:pass@proxy.example.com:8080",
            "https": "https://user:pass@proxy.example.com:8443"
        }
    )
    
    # Find proxy arguments
    http_proxy_arg = None
    https_proxy_arg = None
    for arg in cmd:
        if arg.startswith("--http-proxy="):
            http_proxy_arg = arg
        if arg.startswith("--https-proxy="):
            https_proxy_arg = arg
    
    # Verify format
    assert http_proxy_arg == "--http-proxy=http://user:pass@proxy.example.com:8080"
    assert https_proxy_arg == "--https-proxy=https://user:pass@proxy.example.com:8443"


def test_no_space_in_critical_arguments():
    """Ensure no critical arguments are split into separate list items"""
    cmd = get_streamlink_command(
        streamer_name="test_streamer",
        quality="best",
        output_path="/tmp/test.ts",
        oauth_token="test_token_123",
        supported_codecs="h264,h265",
        proxy_settings={
            "http": "http://proxy.example.com:8080"
        }
    )
    
    # Critical arguments that should use = format
    critical_args = [
        "--twitch-api-header",
        "--twitch-supported-codecs",
        "--http-proxy",
        "--https-proxy"
    ]
    
    # Check each critical argument
    for arg_name in critical_args:
        # Find all occurrences
        matches = [arg for arg in cmd if arg_name in arg]
        
        for match in matches:
            # Verify it uses = format (single argument)
            assert "=" in match, \
                f"{arg_name} must use '=' format, found: {match}"
            
            # Verify it's not followed by a value argument
            idx = cmd.index(match)
            if idx + 1 < len(cmd):
                next_arg = cmd[idx + 1]
                # Next argument should be another option or the URL
                assert next_arg.startswith("--") or "twitch.tv" in next_arg or next_arg in ["best", "/tmp/test.ts"], \
                    f"{arg_name} appears to have value as separate argument: {next_arg}"


def test_command_structure():
    """Test overall command structure"""
    cmd = get_streamlink_command(
        streamer_name="test_streamer",
        quality="best",
        output_path="/tmp/test.ts",
        oauth_token="test_token_123"
    )
    
    # Basic structure checks
    assert cmd[0] == "streamlink"
    assert "--config" in cmd
    assert "twitch.tv/test_streamer" in cmd
    assert "best" in cmd
    assert "-o" in cmd or "--output" in [arg.split("=")[0] for arg in cmd]
    
    # Verify output path
    output_idx = cmd.index("-o") if "-o" in cmd else None
    if output_idx:
        assert cmd[output_idx + 1] == "/tmp/test.ts"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

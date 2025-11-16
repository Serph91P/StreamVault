"""
Streamlink command utility functions for StreamVault.

This module provides utility functions for constructing and executing Streamlink commands,
following the robust approach from the lsdvr project. It handles proxy configuration,
quality settings, and other parameters to ensure reliable stream capture.
"""

import os
import logging
import subprocess
import json
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path

from app.models import GlobalSettings
from app.services.system.logging_service import logging_service

# Get the logger
logger = logging.getLogger(__name__)

def get_streamlink_version() -> str:
    """
    Get the installed version of Streamlink.
    
    Returns:
        String containing the version of Streamlink
    """
    try:
        result = subprocess.run(
            ["streamlink", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        # Extract version number from the output
        version_line = result.stdout.strip()
        # Usually outputs something like "streamlink 5.5.1"
        if version_line:
            parts = version_line.split()
            if len(parts) >= 2:
                return parts[1]  # Return just the version number
        return version_line
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get Streamlink version: {e}")
        return "Unknown"
    except Exception as e:
        logger.error(f"Error getting Streamlink version: {e}")
        return "Error"

def check_proxy_connectivity(proxy_settings: Optional[Dict[str, str]] = None) -> Tuple[bool, str]:
    """
    Check if proxy is reachable before attempting to record.
    
    Args:
        proxy_settings: Optional dictionary containing "http" and/or "https" proxy URLs
        
    Returns:
        Tuple of (is_reachable: bool, error_message: str)
    """
    if not proxy_settings or not any(proxy_settings.values()):
        # No proxy configured, connectivity is assumed OK
        return True, ""
    
    # Test proxy connectivity with a simple Streamlink command
    test_cmd = ["streamlink", "--json", "twitch.tv/test"]
    
    if "http" in proxy_settings and proxy_settings["http"].strip():
        test_cmd.extend(["--http-proxy", proxy_settings["http"].strip()])
    if "https" in proxy_settings and proxy_settings["https"].strip():
        test_cmd.extend(["--https-proxy", proxy_settings["https"].strip()])
    
    try:
        # Use a short timeout to fail fast if proxy is down
        result = subprocess.run(
            test_cmd, 
            capture_output=True, 
            text=True, 
            timeout=10,  # 10 second timeout
            check=False  # Don't raise exception on non-zero exit
        )
        
        # Check for proxy connection errors in stderr
        stderr_lower = result.stderr.lower() if result.stderr else ""
        
        # Common proxy error patterns
        proxy_error_patterns = [
            "unable to connect to proxy",
            "proxy connection failed",
            "connection refused",
            "proxy error",
            "failed to connect",
            "network is unreachable",
            "connection timed out",
            "name or service not known"  # DNS resolution failure
        ]
        
        for pattern in proxy_error_patterns:
            if pattern in stderr_lower:
                error_msg = f"Proxy connectivity check failed: {pattern}"
                logger.error(f"🔴 {error_msg}")
                logger.debug(f"Proxy test stderr: {result.stderr}")
                return False, error_msg
        
        # If we got here without errors, proxy is reachable
        logger.debug("✅ Proxy connectivity check passed")
        return True, ""
        
    except subprocess.TimeoutExpired:
        error_msg = "Proxy connectivity check timed out after 10 seconds"
        logger.error(f"🔴 {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Proxy connectivity check failed with exception: {e}"
        logger.error(f"🔴 {error_msg}")
        return False, error_msg


def get_stream_info(streamer_name: str, proxy_settings: Optional[Dict[str, str]] = None) -> Tuple[bool, Dict[str, Any]]:
    """
    Get information about a stream using Streamlink.
    
    Args:
        streamer_name: The streamer's username
        proxy_settings: Optional dictionary containing "http" and/or "https" proxy URLs
        
    Returns:
        Tuple of (success: bool, info: dict)
        where info contains stream details if successful
    """
    # Check proxy connectivity first if proxy is configured
    if proxy_settings and any(proxy_settings.values()):
        is_reachable, proxy_error = check_proxy_connectivity(proxy_settings)
        if not is_reachable:
            logger.error(f"🔴 PROXY_DOWN: Cannot get stream info for {streamer_name} - {proxy_error}")
            return False, {
                "error": "Proxy connection failed",
                "details": proxy_error,
                "proxy_settings": {k: v[:50] + "..." if len(v) > 50 else v for k, v in proxy_settings.items() if v}
            }
    
    cmd = ["streamlink", "--json", f"twitch.tv/{streamer_name}"]
    
    # Add proxy settings if provided
    if proxy_settings:
        if "http" in proxy_settings and proxy_settings["http"].strip():
            cmd.extend(["--http-proxy", proxy_settings["http"].strip()])
        if "https" in proxy_settings and proxy_settings["https"].strip():
            cmd.extend(["--https-proxy", proxy_settings["https"].strip()])
    
    try:
        logger.debug(f"Running stream info command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        
        # Parse the JSON output
        stream_info = json.loads(result.stdout)
        return True, stream_info
    except subprocess.TimeoutExpired:
        error_msg = "Streamlink command timed out after 30 seconds"
        logger.error(f"🔴 {error_msg} for {streamer_name}")
        return False, {"error": error_msg}
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get stream info for {streamer_name}: {e}")
        logger.debug(f"Command output: {e.stdout}")
        logger.debug(f"Command error: {e.stderr}")
        
        # Check if this is a proxy-related error
        stderr_lower = (e.stderr or "").lower()
        if any(pattern in stderr_lower for pattern in ["proxy", "connection refused", "network unreachable"]):
            return False, {
                "error": "Proxy or network connection failed",
                "stderr": e.stderr,
                "details": "Check proxy settings or network connectivity"
            }
        
        return False, {"error": str(e), "stderr": e.stderr if hasattr(e, 'stderr') else "No error output"}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON output from Streamlink: {e}")
        return False, {"error": f"JSON parse error: {e}", "raw_output": result.stdout if 'result' in locals() else "No output"}
    except Exception as e:
        logger.error(f"Unexpected error getting stream info: {e}")
        return False, {"error": str(e)}

def get_streamlink_command(
    streamer_name: str,
    quality: str,
    output_path: str,
    proxy_settings: Optional[Dict[str, str]] = None,
    force_mode: bool = False,
    log_path: Optional[str] = None,
    supported_codecs: Optional[str] = None,
    oauth_token: Optional[str] = None
) -> List[str]:
    """
    Generate a Streamlink command for recording a stream.
    
    This creates a robust Streamlink command following the approach used in lsdvr (TypeScript),
    with all parameters tuned for maximum stability and quality.
    
    Args:
        streamer_name: The streamer's username
        quality: Quality setting for the stream (e.g. "best", "720p")
        output_path: Full path where the recording should be saved
        proxy_settings: Optional dictionary containing "http" and/or "https" proxy URLs
        force_mode: Use more aggressive settings for difficult connections
        log_path: Custom path for streamlink logs (if None, will use default location)
        supported_codecs: Comma-separated list of codecs (e.g. "h264,h265") - Streamlink 8.0.0+
        oauth_token: Twitch OAuth token for authenticated access (enables H.265/1440p)
        
    Returns:
        List of command arguments for streamlink
    """
    # Make sure we use .ts as intermediate format for better recovery
    if output_path.endswith(".mp4"):
        ts_output_path = output_path.replace(".mp4", ".ts")
    else:
        ts_output_path = output_path
    
    # Use the streamlink log path for this recording session if not provided
    if not log_path:
        log_path = logging_service.get_streamlink_log_path(streamer_name)
    
    # Core streamlink command
    # Note: Most options are in /app/config/streamlink/config.twitch (auto-generated)
    # We MUST specify --config to load our custom config location
    cmd = [
        "streamlink",
        "--config", "/app/config/streamlink/config.twitch",
        f"twitch.tv/{streamer_name}",
        quality,
        "-o", ts_output_path,
        "--logfile", log_path,
    ]
    
    # Note: These settings are now in config.twitch (auto-generated from settings):
    # - --twitch-supported-codecs (codec preferences from database)
    # - --twitch-disable-ads (ad blocking)
    # - --twitch-api-header (OAuth token from environment)
    # - --http-proxy / --https-proxy (proxy settings from database)
    # - --hls-live-edge, --stream-timeout, etc. (stability settings)
    # - --loglevel, --logformat (logging config)
    
    # Only add codec support if explicitly requested (overrides config.twitch)
    if supported_codecs and supported_codecs.strip():
        cmd.extend(["--twitch-supported-codecs", supported_codecs.strip()])
        logger.debug(f"🎨 Overriding codec preference: {supported_codecs}")
    
    # Only add OAuth token if explicitly requested (overrides config.twitch)
    # This allows per-recording OAuth control if needed
    if oauth_token and oauth_token.strip():
        cmd.extend(["--twitch-api-header", f"Authorization=OAuth {oauth_token.strip()}"])
        logger.debug(f"🔑 Using per-recording OAuth token (overrides config)")
    
    # Add proxy settings if provided (overrides config.twitch)
    if proxy_settings:
        cmd = _add_proxy_settings(cmd, proxy_settings, force_mode)
    
    return cmd


def _add_proxy_settings(cmd: List[str], proxy_settings: Dict[str, str], force_mode: bool) -> List[str]:
    """
    Add proxy settings to the Streamlink command.
    
    Args:
        cmd: Existing command list to extend
        proxy_settings: Dictionary with "http" and/or "https" keys for proxy URLs
        force_mode: Whether to use more aggressive settings
        
    Returns:
        Updated command list with proxy settings
    """
    # Add HTTP proxy if configured
    if "http" in proxy_settings and proxy_settings["http"].strip():
        proxy_url = proxy_settings["http"].strip()
        # Validate that the proxy URL has the correct protocol prefix
        if not proxy_url.startswith(('http://', 'https://')):
            error_msg = f"HTTP proxy URL must start with 'http://' or 'https://'. Current value: {proxy_url}"
            logger.error(f"PROXY_VALIDATION_FAILED: {error_msg}")
            raise ValueError(error_msg)
            
        cmd.extend(["--http-proxy", proxy_url])
        logger.debug(f"Using HTTP proxy: {proxy_url}")
        
        # Add proxy-specific optimizations for better audio sync
        cmd.extend([
            "--stream-segment-timeout", "60" if not force_mode else "90",  # Longer timeouts for proxy latency
            "--stream-timeout", "300" if not force_mode else "360",       # Extended overall timeout
            "--hls-segment-queue-threshold", "8",                         # More segments for proxy buffering
            "--stream-segment-attempts", "15" if not force_mode else "20", # More retry attempts
            "--hls-live-edge", "10",                                      # Stay further from live edge to avoid sync issues
            "--ringbuffer-size", "512M",                                 # Larger internal buffer for stable data flow
            "--hls-segment-stream-data",                                  # Write segment data immediately to reduce buffering delays
            "--stream-segment-threads", "2",                             # Use multiple threads for segment downloads
            "--hls-playlist-reload-time", "segment",                     # Optimize playlist reload timing
        ])
                        
    # Add HTTPS proxy if configured
    if "https" in proxy_settings and proxy_settings["https"].strip():
        proxy_url = proxy_settings["https"].strip()
        # Validate that the proxy URL has the correct protocol prefix
        if not proxy_url.startswith(('http://', 'https://')):
            error_msg = f"HTTPS proxy URL must start with 'http://' or 'https://'. Current value: {proxy_url}"
            logger.error(f"PROXY_VALIDATION_FAILED: {error_msg}")
            raise ValueError(error_msg)
            
        cmd.extend(["--https-proxy", proxy_url])
        logger.debug(f"Using HTTPS proxy: {proxy_url}")
        
        # Add proxy-specific optimizations for HTTPS connections too
        cmd.extend([
            "--stream-segment-timeout", "60" if not force_mode else "90",
            "--stream-timeout", "300" if not force_mode else "360",
            "--hls-segment-queue-threshold", "8",
            "--stream-segment-attempts", "15" if not force_mode else "20",
            "--hls-live-edge", "10",
            "--ringbuffer-size", "512M",
        ])
    
    return cmd


def get_proxy_settings_from_db() -> Dict[str, str]:
    """
    Get proxy settings from the database.
    
    Returns:
        Dictionary with http and https proxy settings
    """
    from app.database import SessionLocal
    
    proxy_settings = {}
    
    with SessionLocal() as db:
        global_settings = db.query(GlobalSettings).first()
        if global_settings:
            if global_settings.http_proxy and global_settings.http_proxy.strip():
                proxy_settings["http"] = global_settings.http_proxy.strip()
            if global_settings.https_proxy and global_settings.https_proxy.strip():
                proxy_settings["https"] = global_settings.https_proxy.strip()
    
    return proxy_settings


def get_streamlink_vod_command(
    video_id: str,
    quality: str,
    output_path: str, 
    proxy_settings: Optional[Dict[str, str]] = None,
    force_mode: bool = False
) -> List[str]:
    """
    Generate a Streamlink command for downloading a VOD.
    
    Args:
        video_id: The Twitch VOD ID
        quality: Quality setting for the stream (e.g. "best", "720p")
        output_path: Full path where the VOD should be saved
        proxy_settings: Optional dictionary containing "http" and/or "https" proxy URLs
        force_mode: Use more aggressive settings
        
    Returns:
        List of command arguments for streamlink
    """
    # Find ffmpeg binary path
    ffmpeg_bin: str = os.environ.get("FFMPEG_PATH") or "ffmpeg"  # Use environment variable or default to "ffmpeg"
    
    # Core command for VOD download
    cmd = [
        "streamlink",
        "--ffmpeg-ffmpeg", ffmpeg_bin,
        "-o", output_path,
        "--stream-segment-threads", "10",
        "--url", f"https://www.twitch.tv/videos/{video_id}",
        "--default-stream", quality,
    ]
    
    # Add logging level
    cmd.extend([
        "--loglevel", "debug",
        "--logfile", os.path.join(Path(output_path).parent, f"streamlink_vod_{video_id}.log")
    ])
    
    # Add proxy settings if provided
    if proxy_settings:
        cmd = _add_proxy_settings(cmd, proxy_settings, force_mode)
    
    return cmd


def get_streamlink_clip_command(
    clip_url: str,
    quality: str,
    output_path: str,
    proxy_settings: Optional[Dict[str, str]] = None
) -> List[str]:
    """
    Generate a Streamlink command for downloading a Twitch clip.
    
    Args:
        clip_url: URL to the Twitch clip
        quality: Quality setting (e.g. "best", "720p")
        output_path: Path where the clip should be saved
        proxy_settings: Optional dictionary containing proxy settings
        
    Returns:
        List of command arguments for streamlink
    """
    # Find ffmpeg binary path
    ffmpeg_bin: str = os.environ.get("FFMPEG_PATH") or "ffmpeg"  # Use environment variable or default to "ffmpeg"
    
    # Core command for clip download
    cmd = [
        "streamlink",
        "--ffmpeg-ffmpeg", ffmpeg_bin,
        "-o", output_path,
        "--stream-segment-threads", "10",
        "--url", clip_url,
        "--default-stream", quality,
    ]
    
    # Add logging level
    cmd.extend([
        "--loglevel", "debug",
        "--logfile", os.path.join(Path(output_path).parent, 
                                 f"streamlink_clip_{Path(output_path).stem}.log")
    ])
    
    # Add proxy settings if provided
    if proxy_settings:
        cmd = _add_proxy_settings(cmd, proxy_settings, False)
    
    return cmd

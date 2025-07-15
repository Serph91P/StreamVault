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
# Use lazy imports to avoid circular dependencies
# We'll import logging_service when needed

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
    cmd = ["streamlink", "--json", f"twitch.tv/{streamer_name}"]
    
    # Add proxy settings if provided
    if proxy_settings:
        if "http" in proxy_settings and proxy_settings["http"].strip():
            cmd.extend(["--http-proxy", proxy_settings["http"].strip()])
        if "https" in proxy_settings and proxy_settings["https"].strip():
            cmd.extend(["--https-proxy", proxy_settings["https"].strip()])
    
    try:
        logger.debug(f"Running stream info command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Parse the JSON output
        stream_info = json.loads(result.stdout)
        return True, stream_info
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get stream info for {streamer_name}: {e}")
        logger.debug(f"Command output: {e.stdout}")
        logger.debug(f"Command error: {e.stderr}")
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
    log_path: Optional[str] = None
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
        # Lazy import to avoid circular dependencies
        from importlib import import_module
        logging_service = import_module("app.services.logging_service").logging_service
        log_path = logging_service.get_streamlink_log_path(streamer_name)
    
    # Core streamlink command with enhanced stability parameters
    # Basierend auf den lsdvr-Einstellungen für maximale Stabilität und Ad-Blocking
    cmd = [
        "streamlink",
        f"twitch.tv/{streamer_name}",
        quality,
        "-o", ts_output_path,
        "--hls-live-edge", "99999",
        "--stream-timeout", "200",
        "--stream-segment-timeout", "200",
        "--stream-segment-threads", "5",
        "--ffmpeg-fout", "mpegts",
        "--twitch-disable-ads",  # Ad-Blocking immer aktiviert, unabhängig vom Proxy
        "--retry-streams", "10",
        "--retry-max", "5",
        "--loglevel", "debug",
        "--logfile", log_path,
        "--logformat", "[{asctime}][{name}][{levelname}] {message}",
        "--logdateformat", "%Y-%m-%d %H:%M:%S",
    ]
    
    # Add proxy settings if provided
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

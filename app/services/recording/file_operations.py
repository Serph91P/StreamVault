"""
File operations for the recording service.

This module handles all file-related operations like remuxing and cleanup.
"""

import os
import asyncio
from pathlib import Path
from typing import Optional, TypedDict
from time import monotonic
import logging

from app.config.constants import ASYNC_DELAYS
from app.utils.async_db_utils import run_in_thread_pool

# FFmpeg utilities now handled by background queue system

logger = logging.getLogger("streamvault")


class FfmpegFileOwner(TypedDict):
    pid: int
    name: str
    cmdline: str


def _existing_size(path: str) -> int | None:
    return os.path.getsize(path) if os.path.exists(path) else None


def _remove_stable_ts(ts_path: str, mp4_path: str, previous_size: int) -> bool:
    size = _existing_size(mp4_path)
    if size != previous_size or size is None or size <= 1024 * 1024:
        return False
    try:
        with open(mp4_path, "rb") as file:
            file.read(1024)
        os.remove(ts_path)
        return True
    except Exception as error:
        logger.warning("MP4 file not readable yet, will retry: %s", error)
        return False


async def intelligent_ts_cleanup(
    output_path: str, max_wait_time: int = 1800, psutil_available: bool = False
):
    """Intelligent cleanup that monitors FFmpeg processes and file system for TS to MP4 completion.

    This monitors:
    1. Running FFmpeg processes that might be remuxing our files
    2. File system changes (TS file stable, MP4 file growing)
    3. Process completion signals

    Args:
        output_path: Path to the TS file
        max_wait_time: Maximum time to wait for processing (default: 30 minutes)
        psutil_available: Whether psutil module is available
    """
    try:
        if not output_path.endswith(".ts") or not await run_in_thread_pool(
            os.path.exists, output_path
        ):
            return

        mp4_path = output_path.replace(".ts", ".mp4")
        start_time = monotonic()
        check_interval = 10  # Check every 10 seconds

        logger.info(f"Starting intelligent process-aware TS cleanup for {output_path}")

        while True:
            elapsed = monotonic() - start_time
            if elapsed >= max_wait_time:
                logger.warning(
                    "Process-aware cleanup timeout (%ss), keeping TS file: %s",
                    max_wait_time,
                    output_path,
                )
                return False

            # Check if MP4 file exists and is stable
            mp4_size = await run_in_thread_pool(_existing_size, mp4_path)
            if mp4_size is not None:
                # Check if any FFmpeg processes are working on our files
                active_ffmpeg_processes = (
                    await check_ffmpeg_processes_for_file(output_path, mp4_path)
                    if psutil_available
                    else []
                )

                if not active_ffmpeg_processes:
                    # No FFmpeg processes working on our files, check if MP4 is stable
                    await asyncio.sleep(
                        min(
                            ASYNC_DELAYS.RECORDING_ERROR_RECOVERY,
                            max(0, max_wait_time - (monotonic() - start_time)),
                        )
                    )  # Wait a bit
                    if monotonic() - start_time >= max_wait_time:
                        return False
                    if await run_in_thread_pool(
                        _remove_stable_ts, output_path, mp4_path, mp4_size
                    ):
                        logger.info(
                            "Process-aware cleanup: Removed TS file %s (waited %.0fs)",
                            output_path,
                            monotonic() - start_time,
                        )
                        return True
                else:
                    logger.debug(
                        f"FFmpeg processes still active for our files: {len(active_ffmpeg_processes)} processes"
                    )

            # Wait before next check
            await asyncio.sleep(
                min(check_interval, max(0, max_wait_time - (monotonic() - start_time)))
            )

    except Exception as e:
        logger.error(
            f"Error in process-aware TS cleanup for {output_path}: {e}", exc_info=True
        )


async def check_ffmpeg_processes_for_file(
    ts_path: str, mp4_path: str
) -> list[FfmpegFileOwner]:
    return await run_in_thread_pool(_check_ffmpeg_processes_for_file, ts_path, mp4_path)


def _check_ffmpeg_processes_for_file(
    ts_path: str, mp4_path: str
) -> list[FfmpegFileOwner]:
    """Check for running FFmpeg processes that might be working on our files.

    This uses psutil if available. If not, it returns an empty list.

    Args:
        ts_path: Path to the TS file
        mp4_path: Path to the MP4 file

    Returns:
        List of process information for active FFmpeg processes on our files
    """
    try:
        import psutil

        active_processes = []

        targets = {Path(ts_path).resolve(), Path(mp4_path).resolve()}

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                proc_info = proc.info
                if not proc_info["name"]:
                    continue

                # Check if this is an FFmpeg process
                if "ffmpeg" in proc_info["name"].lower():
                    cmdline = proc_info.get("cmdline", [])
                    if cmdline:
                        cmdline_str = " ".join(cmdline)

                        # Basenames are not ownership: another app may use the same filename.
                        cwd = Path(proc.cwd())
                        arguments = {
                            (
                                (
                                    Path(argument)
                                    if Path(argument).is_absolute()
                                    else cwd / argument
                                ).resolve()
                            )
                            for argument in cmdline
                        }
                        if targets & arguments:
                            active_processes.append(
                                {
                                    "pid": proc_info["pid"],
                                    "name": proc_info["name"],
                                    "cmdline": cmdline_str[
                                        :200
                                    ],  # Truncate for logging
                                }
                            )
                            logger.debug(
                                f"Found active FFmpeg process: PID {proc_info['pid']}"
                            )

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process might have ended or we don't have permission
                continue

        return active_processes

    except ImportError:
        return []
    except Exception as e:
        logger.error(f"Error checking FFmpeg processes: {e}")
        return []


async def find_existing_mp4(recording_dir: str, mp4_path: str) -> Optional[str]:
    return await run_in_thread_pool(_find_existing_mp4, recording_dir, mp4_path)


def _find_existing_mp4(recording_dir: str, mp4_path: str) -> Optional[str]:
    """
    Find existing MP4 file in recording directory

    Returns:
        Optional[str]: Path to existing MP4 file or None if not found
    """
    try:
        # Check if MP4 already exists
        if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 1000000:  # > 1MB
            logger.info(f"Using existing MP4 file: {mp4_path}")
            return mp4_path

        # Look for any MP4 files in recording directory
        recording_path = Path(recording_dir)
        mp4_files = list(recording_path.glob("*.mp4"))

        if mp4_files:
            # Use the largest MP4 file
            largest_mp4 = max(mp4_files, key=lambda p: p.stat().st_size)
            if largest_mp4.stat().st_size > 1000000:  # > 1MB
                logger.info(f"Found existing MP4 file: {largest_mp4}")
                return str(largest_mp4)

        logger.warning(f"No valid MP4 file found in {recording_dir}")
        return None

    except Exception as e:
        logger.error(
            f"Error in find_existing_mp4 for {recording_dir}: {e}", exc_info=True
        )
        return None

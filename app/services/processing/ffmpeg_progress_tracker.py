"""Shared FFmpeg runner with real-time progress reporting.

Wraps ``asyncio.create_subprocess_exec`` for FFmpeg invocations so every
post-processing service emits consistent progress updates to the queue
WebSocket without each service having to re-implement parsing of
``-progress pipe:1`` key=value output.

Usage::

    tracker = FFmpegProgressTracker(logging_service=logging_service)
    return_code, stdout, stderr = await tracker.run(
        cmd=["ffmpeg", "-i", src, ..., dst],
        operation="ts_to_mp4",
        streamer_name=streamer_name,
        progress_callback=lambda pct: queue.update_task_progress(task_id, pct),
        input_path=src,
    )

If ``progress_callback`` is provided, the tracker invokes it with the
current percent (0..99) as new ``-progress`` chunks arrive. ``percent``
is computed from ``out_time_us / total_duration_us`` when an input
duration can be probed via ``ffprobe``; otherwise the callback is never
invoked (UI stays indeterminate).

The tracker injects ``-progress pipe:1 -nostats`` automatically. The
caller's ``cmd`` should NOT already contain ``-progress`` or ``-nostats``.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Tuple, Union

logger = logging.getLogger("streamvault")

ProgressCallback = Callable[[float], Union[None, Awaitable[None]]]

# Hard cap on how often we push progress per task.
_MIN_EMIT_INTERVAL_SECONDS = 0.5
# Smallest percent delta that triggers an emit (to avoid noise).
_MIN_EMIT_DELTA_PERCENT = 1.0


class FFmpegProgressTracker:
    """Run FFmpeg with structured progress reporting via a callback."""

    def __init__(self, logging_service=None):
        self.logging_service = logging_service

    async def run(
        self,
        cmd: List[str],
        *,
        operation: str,
        streamer_name: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
        input_path: Optional[str] = None,
        total_duration_seconds: Optional[float] = None,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[int, bytes, bytes]:
        """Execute ``cmd`` and emit progress updates while it runs.

        Returns ``(return_code, stdout, stderr)``. ``stdout`` excludes the
        ``-progress`` stream that the tracker consumes internally.
        """
        if not cmd or cmd[0] not in ("ffmpeg", "/usr/bin/ffmpeg"):
            # Be liberal: allow any path ending in ``ffmpeg``.
            tail = Path(cmd[0]).name if cmd else ""
            if tail != "ffmpeg":
                raise ValueError(
                    f"FFmpegProgressTracker.run expects an ffmpeg command, got: {cmd[0] if cmd else '<empty>'}"
                )

        # Determine total duration (microseconds) if we can.
        total_us = await self._resolve_total_duration_us(
            total_duration_seconds, input_path
        )

        # Inject -progress pipe:1 -nostats just after the binary so callers
        # don't have to remember to do it. Skip injection if already present.
        instrumented_cmd = list(cmd)
        if "-progress" not in instrumented_cmd:
            instrumented_cmd[1:1] = ["-progress", "pipe:1", "-nostats"]

        # Log invocation via logging_service if available.
        log_path = None
        if self.logging_service is not None and streamer_name:
            try:
                log_path = self.logging_service.log_ffmpeg_start(
                    operation, instrumented_cmd, streamer_name
                )
                if log_path:
                    logger.debug(f"FFmpeg ({operation}) logs: {log_path}")
            except Exception as exc:
                logger.debug(f"logging_service.log_ffmpeg_start failed: {exc}")

        process = await asyncio.create_subprocess_exec(
            *instrumented_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )

        async def _runner():
            stderr_chunks: List[bytes] = []
            stdout_chunks: List[bytes] = []

            async def _consume_stderr():
                assert process.stderr is not None
                while True:
                    chunk = await process.stderr.read(4096)
                    if not chunk:
                        break
                    stderr_chunks.append(chunk)

            async def _consume_progress():
                assert process.stdout is not None
                buf = b""
                last_emit = 0.0
                last_pct = -1.0
                loop = asyncio.get_event_loop()
                # Emit a 0% ping right away so the UI flips to determinate
                # mode immediately if we know the total duration.
                if progress_callback and total_us:
                    await self._emit(progress_callback, 0.0)
                while True:
                    chunk = await process.stdout.read(4096)
                    if not chunk:
                        # Capture trailing partial line (rare for -progress).
                        if buf:
                            stdout_chunks.append(buf)
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        # Pass non-progress lines through to stdout for the
                        # caller's logging.
                        try:
                            text = line.decode("utf-8", errors="ignore").strip()
                        except Exception:
                            continue
                        if not text or "=" not in text:
                            continue
                        key, _, value = text.partition("=")
                        key = key.strip()
                        value = value.strip()
                        if key == "out_time_us" or key == "out_time_ms":
                            # ffmpeg historically wrote out_time_ms but the
                            # value is actually microseconds. Treat both the
                            # same way.
                            try:
                                cur_us = int(value)
                            except ValueError:
                                continue
                            if not (progress_callback and total_us and total_us > 0):
                                continue
                            pct = max(0.0, min(99.0, (cur_us / total_us) * 100.0))
                            now = loop.time()
                            if (
                                pct - last_pct >= _MIN_EMIT_DELTA_PERCENT
                                and (now - last_emit) >= _MIN_EMIT_INTERVAL_SECONDS
                            ):
                                await self._emit(progress_callback, pct)
                                last_emit = now
                                last_pct = pct
                        elif key == "progress" and value == "end":
                            if progress_callback:
                                await self._emit(progress_callback, 99.0)

            await asyncio.gather(_consume_stderr(), _consume_progress())
            await process.wait()
            return b"".join(stdout_chunks), b"".join(stderr_chunks)

        try:
            if timeout is not None:
                stdout, stderr = await asyncio.wait_for(_runner(), timeout=timeout)
            else:
                stdout, stderr = await _runner()
        except asyncio.TimeoutError:
            logger.error(f"FFmpeg ({operation}) timed out after {timeout}s; killing")
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
            raise
        except Exception:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            raise

        if self.logging_service is not None and streamer_name:
            try:
                self.logging_service.log_ffmpeg_output(
                    operation, stdout, stderr, process.returncode, streamer_name
                )
            except Exception as exc:
                logger.debug(f"logging_service.log_ffmpeg_output failed: {exc}")

        return process.returncode or 0, stdout, stderr

    async def _resolve_total_duration_us(
        self,
        total_duration_seconds: Optional[float],
        input_path: Optional[str],
    ) -> Optional[int]:
        if total_duration_seconds is not None and total_duration_seconds > 0:
            return int(total_duration_seconds * 1_000_000)
        if not input_path:
            return None
        try:
            probe = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(input_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, _ = await asyncio.wait_for(probe.communicate(), timeout=10)
            text = out.decode("utf-8", errors="ignore").strip()
            if not text:
                return None
            seconds = float(text)
            if seconds <= 0:
                return None
            return int(seconds * 1_000_000)
        except (asyncio.TimeoutError, FileNotFoundError, ValueError):
            return None
        except Exception as exc:
            logger.debug(f"ffprobe duration lookup failed for {input_path}: {exc}")
            return None

    async def _emit(self, callback: ProgressCallback, percent: float) -> None:
        try:
            result = callback(percent)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            logger.debug(f"FFmpeg progress callback failed at {percent:.1f}%: {exc}")


# Module-level singleton wired up lazily by callers.
_default_tracker: Optional[FFmpegProgressTracker] = None


def get_ffmpeg_progress_tracker(logging_service=None) -> FFmpegProgressTracker:
    """Return a shared tracker instance, lazily binding services on first use."""
    global _default_tracker
    if _default_tracker is None:
        _default_tracker = FFmpegProgressTracker(logging_service=logging_service)
    elif logging_service is not None and _default_tracker.logging_service is None:
        _default_tracker.logging_service = logging_service
    return _default_tracker

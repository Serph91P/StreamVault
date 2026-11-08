"""Single-owner, bounded and redacted diagnostic drains for recording children."""

import asyncio

from app.utils.security import StreamingStreamlinkOutputSanitizer


class BoundedStreamlinkOutput:
    TAIL_BYTES = 64 * 1024
    MAX_LINE_BYTES = 64 * 1024
    CHUNK_BYTES = 8192
    FAILURE_MARKERS = (
        "ProxyError",
        "Tunnel connection failed",
        "Unable to open URL",
        "No playable streams found",
    )

    def __init__(self, process, known_secrets=()):
        self.process = process
        self._readers = tuple(
            asyncio.create_task(self.drain_reader(reader, known_secrets))
            for reader in (process.stdout, process.stderr)
        )
        self._completion = asyncio.create_task(self._finish())

    @classmethod
    async def drain_reader(cls, reader, known_secrets=()):
        # Recording's package exports ProcessManager, which imports this utility.
        from app.services.recording.recording_auth_policy import (
            is_twitch_auth_rejection,
        )

        if reader is None:
            return b""
        sanitizer = StreamingStreamlinkOutputSanitizer(known_secrets)
        pending = b""
        discarding_line = False
        tail = b""
        scan_tail = ""
        markers = set()

        def retain(safe):
            nonlocal tail, scan_tail
            scan = scan_tail + safe
            lower = scan.lower()
            if (
                "Authorization token invalid" not in markers
                and ("token" in lower or "401" in scan)
                and is_twitch_auth_rejection(scan)
            ):
                markers.add("Authorization token invalid")
            markers.update(marker for marker in cls.FAILURE_MARKERS if marker in scan)
            scan_tail = scan[-512:]
            tail = (tail + safe.encode("utf-8"))[-cls.TAIL_BYTES :]

        while chunk := await reader.read(cls.CHUNK_BYTES):
            complete = []
            for part in chunk.splitlines(keepends=True):
                terminated = part.endswith((b"\n", b"\r"))
                if not discarding_line:
                    pending += part
                    if len(pending) > cls.MAX_LINE_BYTES:
                        # Discard the WHOLE overlong line, not a URL/token fragment.
                        pending = b""
                        discarding_line = True
                        complete.append(b"[overlong diagnostic line omitted]\n")
                if terminated:
                    if not discarding_line:
                        complete.append(pending)
                    pending = b""
                    discarding_line = False
            if complete:
                retain(sanitizer.feed(b"".join(complete)))
        if pending and not discarding_line:
            retain(sanitizer.feed(pending))
        retain(sanitizer.flush())
        prefix = ("\n".join(sorted(markers)) + "\n").encode() if markers else b""
        return prefix + tail[-(cls.TAIL_BYTES - len(prefix)) :]

    async def _finish(self):
        output = await asyncio.gather(*self._readers)
        await self.process.wait()
        return tuple(output)

    async def wait(self):
        # Cancelling one consumer must not cancel pipe ownership during rotation.
        return await asyncio.shield(self._completion)

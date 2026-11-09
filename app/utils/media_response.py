"""Native Range/HEAD delivery with a finite full-response media snapshot."""

import anyio
from starlette.responses import FileResponse
from starlette.types import Send


class SnapshotFileResponse(FileResponse):
    async def _handle_simple(
        self, send: Send, send_header_only: bool, send_pathsend: bool
    ) -> None:
        # Starlette 1.6 reads to EOF; a live capture can outgrow Content-Length.
        # Path-send cannot enforce this bound, so full transfers use bounded reads.
        remaining = int(self.headers["content-length"])
        if send_header_only:
            await send(
                {
                    "type": "http.response.start",
                    "status": self.status_code,
                    "headers": self.raw_headers,
                }
            )
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            return
        async with await anyio.open_file(self.path, mode="rb") as media:
            await send(
                {
                    "type": "http.response.start",
                    "status": self.status_code,
                    "headers": self.raw_headers,
                }
            )
            while remaining:
                data = await media.read(min(self.chunk_size, remaining))
                if not data:
                    raise RuntimeError("Media shrank during snapshot delivery")
                remaining -= len(data)
                await send(
                    {
                        "type": "http.response.body",
                        "body": data,
                        "more_body": remaining > 0,
                    }
                )
            if not int(self.headers["content-length"]):
                await send(
                    {"type": "http.response.body", "body": b"", "more_body": False}
                )

"""Application-owned bounded HTTP transport; endpoint adapters own retry policy."""

import asyncio
import logging
import ssl
from contextvars import ContextVar
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http.cookiejar import Cookie, CookieJar
from typing import Literal

import httpx

from app.utils.async_db_utils import run_in_thread_pool


_managed_request: ContextVar[bool] = ContextVar("managed_http_request", default=False)


class _TransportLogPrivacy(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if _managed_request.get():
            args = record.args
            if (
                record.name == "httpx"
                and isinstance(args, tuple)
                and len(args) >= 4
                and isinstance(args[3], int)
            ):
                record.msg = "Managed HTTP request: method=%s status=%s"
                record.args = (args[0], args[3])
            else:
                # httpcore DEBUG includes response headers, cookies and exception values.
                record.msg = "Managed HTTP transport event"
                record.args = ()
        return True


_transport_log_privacy = _TransportLogPrivacy()


@dataclass(frozen=True, slots=True)
class HTTPPolicy:
    connect_timeout: float = 5.0
    read_timeout: float = 20.0
    write_timeout: float = 20.0
    pool_timeout: float = 5.0
    total_timeout: float = 30.0
    max_connections: int = 20
    max_keepalive_connections: int = 10
    max_response_bytes: int = 2 * 1024 * 1024
    max_redirects: int = 10


@dataclass(frozen=True, slots=True)
class HTTPReply:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True, slots=True)
class HTTPStreamReply:
    status_code: int
    headers: Mapping[str, str]
    chunks: AsyncIterator[bytes]


class HTTPClientError(RuntimeError):
    def __init__(
        self,
        code: Literal["closed", "timeout", "network", "response_too_large", "status"],
        *,
        status_code: int | None = None,
    ) -> None:
        self.code = code
        self.status_code = status_code
        # Neither upstream URLs nor response/credential values enter exception logs.
        super().__init__(f"External HTTP request failed: {code}")


class _NoCookies(CookieJar):
    def set_cookie(self, cookie: Cookie) -> None:
        # Pool connections without changing the old per-request cookie isolation.
        return None


class ManagedHTTPClient:
    def __init__(self, policy: HTTPPolicy) -> None:
        self.policy = policy
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()
        self._closed = False
        self._close_task: asyncio.Task[None] | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        async with self._lock:
            if self._closed:
                raise HTTPClientError("closed")
            for name in ("httpx", "httpcore.connection", "httpcore.http11"):
                logging.getLogger(name).addFilter(_transport_log_privacy)
            if self._client is None:
                # Loading system CA files is blocking I/O, never factory/import work.
                context = await run_in_thread_pool(ssl.create_default_context)
                self._client = httpx.AsyncClient(
                    verify=context,
                    trust_env=False,
                    cookies=_NoCookies(),
                    headers={"User-Agent": "StreamVault"},
                    timeout=httpx.Timeout(
                        connect=self.policy.connect_timeout,
                        read=self.policy.read_timeout,
                        write=self.policy.write_timeout,
                        pool=self.policy.pool_timeout,
                    ),
                    limits=httpx.Limits(
                        max_connections=self.policy.max_connections,
                        max_keepalive_connections=self.policy.max_keepalive_connections,
                    ),
                    follow_redirects=False,
                    max_redirects=self.policy.max_redirects,
                )
            return self._client

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str | Sequence[str]] | None = None,
        data: Mapping[str, str] | None = None,
        json: object = None,
        follow_redirects: bool = False,
    ) -> HTTPReply:
        async with self.stream(
            method,
            url,
            headers=headers,
            params=params,
            data=data,
            json=json,
            follow_redirects=follow_redirects,
        ) as response:
            chunks = [chunk async for chunk in response.chunks]
            return HTTPReply(response.status_code, response.headers, b"".join(chunks))

    async def _limited_chunks(self, response: httpx.Response) -> AsyncIterator[bytes]:
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > self.policy.max_response_bytes:
                raise HTTPClientError("response_too_large")
            yield chunk

    @asynccontextmanager
    async def stream(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str | Sequence[str]] | None = None,
        data: Mapping[str, str] | None = None,
        json: object = None,
        follow_redirects: bool = False,
    ) -> AsyncIterator[HTTPStreamReply]:
        log_context = _managed_request.set(True)
        try:
            async with asyncio.timeout(self.policy.total_timeout):
                client = await self._get_client()
                async with client.stream(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    data=data,
                    json=json,
                    follow_redirects=follow_redirects,
                ) as response:
                    if not 200 <= response.status_code < 300:
                        raise HTTPClientError(
                            "status", status_code=response.status_code
                        )
                    yield HTTPStreamReply(
                        response.status_code,
                        dict(response.headers),
                        self._limited_chunks(response),
                    )
        except (httpx.TimeoutException, TimeoutError):
            raise HTTPClientError("timeout") from None
        except (httpx.RequestError, httpx.InvalidURL):
            raise HTTPClientError("network") from None
        finally:
            _managed_request.reset(log_context)

    async def close(self) -> None:
        async with self._lock:
            self._closed = True
            if self._client is not None and self._close_task is None:
                self._close_task = asyncio.create_task(
                    self._client.aclose(), name="streamvault:http-client-close"
                )
            task = self._close_task
        if task is not None:
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                while not task.done():
                    try:
                        await asyncio.shield(task)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                if not task.cancelled():
                    task.exception()
                raise

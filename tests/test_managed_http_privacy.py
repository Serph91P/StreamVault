"""Transport logging must not expose credential-bearing provider URLs."""

import logging
import asyncio

import pytest

from tests.test_managed_http_client import server, types


@pytest.mark.asyncio
async def test_malformed_provider_url_is_a_safe_typed_failure():
    Client, Policy, Error = types()
    client = Client(Policy())
    marker = "fixture-private-port"
    try:
        with pytest.raises(Error) as error:
            await client.request("GET", f"http://127.0.0.1:{marker}/image")
        assert error.value.code == "network"
        assert marker not in str(error.value)
    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["ok", "denied"])
async def test_managed_transport_redacts_its_own_httpx_url_without_changing_other_contexts(
    path, caplog
):
    Client, Policy, Error = types()
    client = Client(Policy())
    caplog.set_level(logging.DEBUG)
    marker = "fixture-private-url-token"
    try:
        async with server() as (base, _, _, _):
            url = f"{base}/{path}?signature={marker}"
            if path == "denied":
                with pytest.raises(Error):
                    await client.request("GET", url)
            else:
                assert (await client.request("GET", url)).body == b"ok"
            owned = "\n".join(
                record.getMessage()
                for record in caplog.records
                if record.name == "streamvault"
                or record.name.startswith(("httpx", "httpcore"))
            )
            assert marker not in owned
            assert url not in owned
            assert "must-not-be-replayed" not in owned
            logging.getLogger("httpx").info("outside-context-diagnostic")
            assert "outside-context-diagnostic" in caplog.text
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_transport_privacy_is_task_scoped_and_resets_on_cancellation(caplog):
    Client, Policy, Error = types()
    client = Client(Policy())
    caplog.set_level(logging.DEBUG)
    operation = None
    try:
        async with server() as (base, _, entered, release):

            async def consume():
                try:
                    return await client.request(
                        "GET", base + "/slow?signature=fixture-cancelled-private"
                    )
                except asyncio.CancelledError:
                    logging.getLogger("httpx").info("cancelled-task-context-restored")
                    raise

            operation = asyncio.create_task(consume())
            assert await asyncio.wait_for(entered.wait(), 5)
            logging.getLogger("httpx").info("unrelated-concurrent-context")
            assert "unrelated-concurrent-context" in caplog.text
            operation.cancel()
            with pytest.raises(asyncio.CancelledError):
                await operation
            release.set()
            logging.getLogger("httpx").info("after-cancellation-context")
            assert "after-cancellation-context" in caplog.text
            assert "cancelled-task-context-restored" in caplog.text
    finally:
        if operation is not None:
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
        await client.close()

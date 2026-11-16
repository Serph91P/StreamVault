"""An owner cannot abandon refresh cleanup when shutdown is cancelled."""

import asyncio

import pytest

from app.services.api.twitch_api import TwitchAPIService


@pytest.mark.asyncio
async def test_twitch_shutdown_drains_refresh_cleanup_after_repeated_cancellation():
    client = TwitchAPIService()
    entered, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    cleaned = False

    async def fetch():
        nonlocal cleaned
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()
            cleaned = True

    client._fetch_access_token = fetch
    waiter = asyncio.create_task(client.get_access_token())
    closer = None
    try:
        await asyncio.wait_for(entered.wait(), 2)
        closer = asyncio.create_task(client.close())
        await asyncio.wait_for(cleaning.wait(), 2)
        closer.cancel()
        await asyncio.sleep(0)
        closer.cancel()
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await closer
        assert cleaned, "shutdown must retain refresh cleanup until it really finishes"
        assert client._token_refresh.done()
    finally:
        release.set()
        await client.close()
        await asyncio.gather(waiter, *([closer] if closer else []), return_exceptions=True)

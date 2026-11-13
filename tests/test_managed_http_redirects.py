"""Image GET redirects are opt-in, bounded, and do not change Helix defaults."""

from collections import Counter

import pytest
from aiohttp import web

from tests.test_managed_http_client import types


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_image_redirect_opt_in_preserves_default_status_and_cookie_isolation(
    streaming,
):
    Client, Policy, Error = types()
    seen = []

    async def serve(request):
        seen.append((request.path, request.headers.get("Cookie")))
        if request.path == "/redirect":
            response = web.HTTPFound("/image")
            response.set_cookie("credential", "fixture-private-cookie")
            raise response
        return web.Response(body=b"image-bytes", content_type="image/jpeg")

    app = web.Application()
    app.router.add_get("/{path}", serve)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    url = f"http://127.0.0.1:{runner.addresses[0][1]}"
    client = Client(Policy())
    try:
        with pytest.raises(Error) as error:
            await client.request("GET", url + "/redirect")
        assert error.value.code == "status" and error.value.status_code == 302
        assert seen == [("/redirect", None)]
        if streaming:
            async with client.stream(
                "GET", url + "/redirect", follow_redirects=True
            ) as reply:
                assert reply.status_code == 200
                assert (
                    b"".join([chunk async for chunk in reply.chunks]) == b"image-bytes"
                )
        else:
            assert (
                await client.request("GET", url + "/redirect", follow_redirects=True)
            ).body == b"image-bytes"
        assert seen == [("/redirect", None), ("/redirect", None), ("/image", None)]
    finally:
        await client.close()
        await runner.cleanup()


@pytest.mark.asyncio
async def test_image_redirect_chain_is_bounded_without_general_http_retries():
    Client, Policy, Error = types()
    seen = Counter()

    async def redirect(request):
        seen[request.path] += 1
        raise web.HTTPFound("/loop")

    app = web.Application()
    app.router.add_get("/loop", redirect)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    url = f"http://127.0.0.1:{runner.addresses[0][1]}/loop"
    client = Client(Policy(max_redirects=1))
    try:
        with pytest.raises(Error) as error:
            await client.request("GET", url, follow_redirects=True)
        assert error.value.code == "network"
        assert url not in str(error.value)
        assert seen == {"/loop": 2}
    finally:
        await client.close()
        await runner.cleanup()

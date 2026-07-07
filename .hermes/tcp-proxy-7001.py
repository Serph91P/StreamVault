import asyncio

TARGET_HOST = "192.168.96.3"
TARGET_PORT = 7000
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 7001

async def pipe(reader, writer):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()

async def handle(client_reader, client_writer):
    try:
        target_reader, target_writer = await asyncio.open_connection(TARGET_HOST, TARGET_PORT)
    except Exception:
        client_writer.close()
        await client_writer.wait_closed()
        return
    await asyncio.gather(pipe(client_reader, target_writer), pipe(target_reader, client_writer), return_exceptions=True)

async def main():
    server = await asyncio.start_server(handle, LISTEN_HOST, LISTEN_PORT)
    print(f"proxy {LISTEN_HOST}:{LISTEN_PORT} -> {TARGET_HOST}:{TARGET_PORT}", flush=True)
    async with server:
        await server.serve_forever()

asyncio.run(main())

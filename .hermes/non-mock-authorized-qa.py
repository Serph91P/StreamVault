import asyncio
import hashlib
import json
import secrets
import subprocess
from datetime import datetime, timezone

import httpx
import websockets

CONTAINER = "streamvault-develop"
BASE = "http://127.0.0.1:7001"
WS = "ws://localhost:7001/ws"
HOST_HEADER = {"Host": "localhost", "Accept": "application/json"}


def docker_py(code: str) -> str:
    proc = subprocess.run(["docker", "exec", "-i", CONTAINER, "python", "-"], input=code, text=True, capture_output=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"docker python failed: {proc.stderr}\nSTDOUT:\n{proc.stdout}")
    return proc.stdout.strip()


def create_session_and_seed_streamer():
    raw = "qa_" + secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    code = f'''
from app.database import SessionLocal
from app.models import User, Session, Streamer, SystemConfig
from datetime import datetime, timezone
import json
raw = {raw!r}
token_hash = {token_hash!r}
with SessionLocal() as db:
    user = db.query(User).filter_by(is_admin=True).first()
    if not user:
        raise SystemExit("no admin user")
    db.query(Session).filter_by(token=token_hash).delete()
    db.add(Session(user_id=user.id, token=token_hash, created_at=datetime.now(timezone.utc)))
    streamer = db.query(Streamer).filter_by(username="summit1g").first()
    if not streamer:
        streamer = Streamer(username="summit1g", twitch_id="26490481", is_test_data=True)
        db.add(streamer)
    db.commit()
    cfg = {{c.key: bool(c.value) for c in db.query(SystemConfig).filter(SystemConfig.key.in_(["vapid_public_key","vapid_private_key","vapid_claims_sub"])).all()}}
    print(json.dumps({{"user_id": user.id, "username": user.username, "session_token": raw, "streamer_id": streamer.id, "vapid_config_rows": cfg}}))
'''
    output = docker_py(code)
    return json.loads(output.splitlines()[-1])


async def main():
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "container": CONTAINER,
        "base_url": BASE,
        "authorization": "Max approved creating temporary QA session and test prerequisites in the running backend",
        "steps": [],
        "gates": {},
    }
    seed = create_session_and_seed_streamer()
    token = seed.pop("session_token")
    result["seed"] = seed
    headers = {**HOST_HEADER, "Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        for path in ["/auth/check", "/api/live/active", "/api/push/debug", "/api/push/vapid-public-key"]:
            try:
                r = await client.get(BASE + path)
                result["steps"].append({"method": "GET", "path": path, "status": r.status_code, "body": r.text[:1000]})
            except Exception as exc:
                result["steps"].append({"method": "GET", "path": path, "error": repr(exc)})

        ws_messages = []
        try:
            async with websockets.connect(WS, additional_headers={"Authorization": f"Bearer {token}"}) as ws:
                ws_messages.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=10)))
                post = await client.post(BASE + "/api/settings/test-websocket-notification")
                result["steps"].append({"method": "POST", "path": "/api/settings/test-websocket-notification", "status": post.status_code, "body": post.text[:1000]})
                ws_messages.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=10)))
            result["gates"]["websocket"] = {"status": "passed", "messages": ws_messages}
        except Exception as exc:
            result["gates"]["websocket"] = {"status": "failed", "error": repr(exc), "messages": ws_messages}

        try:
            start = await client.post(BASE + "/api/live/start/summit1g", json={"quality": "best", "supported_codecs": "h264"})
            result["steps"].append({"method": "POST", "path": "/api/live/start/summit1g", "status": start.status_code, "body": start.text[:1200]})
            if start.status_code == 200:
                start_json = start.json()
                playlist_url = start_json["playlist_url"]
                playlist = None
                playlist_status = None
                for _attempt in range(1, 16):
                    pr = await client.get(BASE + playlist_url)
                    playlist_status = pr.status_code
                    if pr.status_code == 200 and "#EXTM3U" in pr.text:
                        playlist = pr.text
                        break
                    await asyncio.sleep(2)
                result["gates"]["hls_playback"] = {
                    "status": "passed" if playlist else "failed",
                    "session_id": start_json.get("session_id"),
                    "playlist_url": playlist_url,
                    "playlist_status": playlist_status,
                    "playlist_head": playlist[:500] if playlist else None,
                }
                await client.delete(BASE + f"/api/live/stop/{start_json['session_id']}")
            else:
                result["gates"]["hls_playback"] = {"status": "failed", "start_status": start.status_code, "body": start.text[:1000]}
        except Exception as exc:
            result["gates"]["hls_playback"] = {"status": "failed", "error": repr(exc)}

        try:
            local = await client.post(BASE + "/api/push/test-local")
            debug = await client.get(BASE + "/api/push/debug")
            key = await client.get(BASE + "/api/push/vapid-public-key")
            result["gates"]["push_server_flow"] = {
                "status": "passed" if local.status_code == 200 and debug.status_code == 200 else "failed",
                "test_local_status": local.status_code,
                "test_local_body": local.text[:1000],
                "debug_status": debug.status_code,
                "debug_body": debug.text[:1000],
                "vapid_status": key.status_code,
                "vapid_body": key.text[:1000],
            }
        except Exception as exc:
            result["gates"]["push_server_flow"] = {"status": "failed", "error": repr(exc)}

    print(json.dumps(result, indent=2, sort_keys=True))

asyncio.run(main())

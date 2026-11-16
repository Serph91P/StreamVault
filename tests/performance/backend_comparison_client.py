"""Executed inside an isolated app container after ordinary lifespan startup."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
from secrets import token_urlsafe
import statistics
import time

import httpx
from sqlalchemy import insert
from websockets.sync.client import connect

from app.database import SessionLocal, engine
from app.models import Recording, Stream, Streamer
from app.services.media.video_catalog_service import VideoCatalogService

root = Path("/recordings")
media = root / "fixture.mp4"
media.write_bytes(b"synthetic catalog fixture; no decoded-media claim")
started = datetime(2026, 11, 1, tzinfo=timezone.utc)
with engine.begin() as connection:
    connection.execute(
        insert(Streamer),
        [
            {"id": i, "username": f"channel-{i}", "twitch_id": f"synthetic-{i}"}
            for i in range(1, 21)
        ],
    )
    connection.execute(
        insert(Stream),
        [
            {
                "id": i,
                "streamer_id": (i - 1) % 20 + 1,
                "title": f"Stream {i}",
                "recording_path": str(media),
                "started_at": started - timedelta(hours=i),
                "ended_at": started - timedelta(hours=i - 1),
            }
            for i in range(1, 2001)
        ],
    )
    connection.execute(
        insert(Recording),
        [
            {
                "id": i,
                "stream_id": i,
                "status": "completed",
                "path": str(media),
                "start_time": started - timedelta(hours=i),
            }
            for i in range(1, 2001)
        ],
    )
# Both trees already expose this native bounded reconciler; no fabricated index.
cursor = 0
while True:
    with SessionLocal() as db:
        cursor, count = VideoCatalogService(db).reconcile_batch(after_id=cursor)
    if not count:
        break


def describe(samples):
    values = sorted(samples)
    return {
        "n": len(samples),
        "median": statistics.median(values),
        "p95": values[int((len(values) - 1) * 0.95)],
        "raw": samples,
    }


base = "http://127.0.0.1:7000"
result = {
    "fixture": {
        "streamers": 20,
        "streams": 2000,
        "recordings": 2000,
        "read_iterations": 30,
        "concurrency": 1,
    },
    "reads": {},
}
with httpx.Client(base_url=base, timeout=45) as client:
    credentials = {"username": "benchmark-admin", "password": token_urlsafe(32)}
    setup = client.post("/auth/setup", json=credentials)
    setup.raise_for_status()
    client.post("/auth/login", json=credentials).raise_for_status()
    # Loopback HTTP intentionally doesn't resend Secure cookies. Exercise the
    # already-supported Bearer transport without changing cookie policy.
    client.headers["Authorization"] = "Bearer " + client.cookies["access_token"]
    for path in [
        "/api/health/live",
        "/api/streamers",
        "/api/videos/catalog?page=1&page_size=50",
        "/api/recording/active",
    ]:
        warmup = client.get(path)
        warmup.raise_for_status()
        if path.startswith("/api/videos"):
            assert len(warmup.json()["items"]) == 50, warmup.text[:200]
        times, queries, query_seconds, sizes = [], [], [], []
        for _ in range(30):
            start = time.perf_counter()
            response = client.get(path)
            times.append(time.perf_counter() - start)
            response.raise_for_status()
            queries.append(int(response.headers["x-benchmark-query-count"]))
            query_seconds.append(float(response.headers["x-benchmark-query-seconds"]))
            sizes.append(len(response.content))
        result["reads"][path] = {
            "elapsed_seconds": describe(times),
            "query_count": describe(queries),
            "query_seconds": describe(query_seconds),
            "response_bytes": describe(sizes),
        }
    acknowledgements = []
    for i in range(30):
        identifier = f"benchmark-{i}"
        timestamp = datetime.now(timezone.utc).isoformat()
        body = json.dumps(
            {"challenge": "synthetic-challenge"}, separators=(",", ":")
        ).encode()
        signature = (
            "sha256="
            + hmac.new(
                b"benchmark-eventsub-secret",
                identifier.encode() + timestamp.encode() + body,
                hashlib.sha256,
            ).hexdigest()
        )
        start = time.perf_counter()
        response = client.post(
            "/eventsub",
            content=body,
            headers={
                "Twitch-Eventsub-Message-Id": identifier,
                "Twitch-Eventsub-Message-Timestamp": timestamp,
                "Twitch-Eventsub-Message-Signature": signature,
                "Twitch-Eventsub-Message-Type": "webhook_callback_verification",
            },
        )
        acknowledgements.append(time.perf_counter() - start)
        assert response.status_code == 200 and response.text == "synthetic-challenge"
    result["eventsub_ack_seconds"] = describe(acknowledgements)
    cookies = "; ".join(f"{key}={value}" for key, value in client.cookies.items())
    broadcasts = []
    with connect(
        "ws://127.0.0.1:7000/ws", additional_headers={"Cookie": cookies}, origin=base
    ) as socket:
        for sequence in range(30):
            start = time.perf_counter()
            client.post(
                f"/api/__benchmark/broadcast?sequence={sequence}"
            ).raise_for_status()
            while True:
                payload = json.loads(socket.recv(timeout=10))
                if (
                    payload.get("type") == "benchmark.event"
                    and payload.get("data", {}).get("sequence") == sequence
                ):
                    break
            broadcasts.append(time.perf_counter() - start)
    result["websocket_roundtrip_seconds"] = describe(broadcasts)
    result["catalog_profile"] = (
        client.post("/api/__benchmark/profile").raise_for_status().json()
    )
    result["queue"] = client.post("/api/__benchmark/queue").raise_for_status().json()
    children = [
        client.post("/api/__benchmark/child")
        .raise_for_status()
        .json()["startup_and_reap_seconds"]
        for _ in range(30)
    ]
    result["synthetic_capture_child_start_and_reap_seconds"] = describe(children)
    result["recording_process"] = (
        client.post("/api/__benchmark/recording-process").raise_for_status().json()
    )
    result["resources_after_workload"] = (
        client.get("/api/__benchmark/resources").raise_for_status().json()
    )
print(json.dumps(result, sort_keys=True))

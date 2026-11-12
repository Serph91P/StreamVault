"""Initialized, logged-out real factory asset gate; no ASGI/route/dependency overlays.

Default: inspect the actual compiled worker and require every precache resource.
--icons-only is the focused regression, not a complete PWA/browser acceptance.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[1]
ICONS = (
    "maskable-icon-512x512.png",
    "maskable-icon-192x192.png",
    "icon-512x512.png",
)


async def inspect_assets(frontend: Path, icons_only: bool) -> dict:
    import httpx
    from app.database import Base, SessionLocal, database_lifecycle
    from app.models import User
    from app.main import create_app

    # Explicit SQLite DDL transaction avoids per-index filesystem sync in this fixture.
    with database_lifecycle.sync_engine.begin() as connection:
        connection.exec_driver_sql("BEGIN")
        Base.metadata.create_all(connection)
    with SessionLocal() as db:
        db.add(
            User(
                username="synthetic-asset-admin",
                password="not-a-login-hash",
                is_admin=True,
                is_active=True,
            )
        )
        db.commit()
    application = create_app()
    assert not application.dependency_overrides
    if icons_only:
        entries = list(ICONS)
    else:
        worker = (frontend / "dist/sw.js").read_text()
        entries = re.findall(r'\{url:"([^"]+)",revision:(?:"[^"]+"|null)\}', worker)
        assert entries and len(entries) == len(set(entries)), (
            "No unique real compiled precache inventory"
        )
        assert all(icon in entries for icon in ICONS), (
            "Original icon coverage must remain"
        )
    observations = []
    failures = []
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="http://127.0.0.1",
        follow_redirects=False,
    ) as client:
        for entry in entries:
            path = urljoin("/sw.js", entry)
            print(f"Requesting compiled resource {path}", flush=True)
            try:
                response = await asyncio.wait_for(client.get(path), timeout=5.0)
            except TimeoutError:
                raise AssertionError(
                    f"Factory resource request timed out: {path}"
                ) from None
            relative = (
                path.removeprefix("/pwa/")
                if path.startswith("/pwa/")
                else path.lstrip("/")
            )
            expected = frontend / "dist" / relative
            if not expected.is_file():
                expected = frontend / "public" / relative
            correct_bytes = (
                expected.is_file() and response.content == expected.read_bytes()
            )
            row = {
                "url": path,
                "status": response.status_code,
                "bytes": len(response.content),
                "location": response.headers.get("location"),
                "correct_bytes": correct_bytes,
            }
            if path.endswith(".png"):
                row["png_content"] = response.headers.get(
                    "content-type"
                ) == "image/png" and response.content.startswith(b"\x89PNG\r\n\x1a\n")
            observations.append(row)
            if (
                response.status_code != 200
                or not response.content
                or not correct_bytes
                or row.get("png_content") is False
            ):
                failures.append(row)
        protected = []
        for path in (
            "/icon-512x512.png/private",
            "/maskable-icon-private.png",
            "/icon-512x512.png.json",
            "/api/system/info",
            "/api/admin/recordings",
            "/recordings/private.ts",
        ):
            response = await client.get(path)
            protected.append(
                {
                    "url": path,
                    "status": response.status_code,
                    "location": response.headers.get("location"),
                }
            )
            assert (
                response.status_code == 307
                and response.headers.get("location") == "/auth/login"
            ), protected[-1]
        if not icons_only:
            worker_response = await client.get("/sw.js")
            assert worker_response.status_code == 200
            assert "importScripts('/pwa/push-sw.js')" in worker_response.text
            assert worker_response.headers["service-worker-allowed"] == "/"
            assert (await client.get("/pwa/push-sw.js")).status_code == 200
            login = await client.get("/auth/login")
            assert (
                login.status_code == 200
                and login.content == (frontend / "dist/index.html").read_bytes()
            )
    database_lifecycle.dispose_sync()
    return {
        "scope": "initialized logged-out factory ASGI; no lifespan, browser, login or PostgreSQL acceptance",
        "mode": "icons-only" if icons_only else "actual-compiled-precache",
        "dependency_overrides": 0,
        "route_overlays": 0,
        "precache_count": len(observations),
        "precache": observations,
        "protected_controls": protected,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--icons-only", action="store_true")
    arguments = parser.parse_args()
    frontend = arguments.frontend_root.resolve()
    output = arguments.output.resolve()
    with tempfile.TemporaryDirectory(
        prefix="842-asset-factory-", dir=os.environ.get("TMPDIR")
    ) as temporary:
        runtime = Path(temporary)
        (runtime / "app").mkdir()
        (runtime / "app/frontend").symlink_to(frontend, target_is_directory=True)
        (runtime / "app/data").mkdir()
        os.chdir(runtime)
        os.environ.update(
            ENVIRONMENT="test",
            BASE_DIR=str(runtime),
            BASE_URL="http://127.0.0.1",
            DATABASE_URL=f"sqlite:///{runtime / 'fixture.sqlite'}",
            TWITCH_APP_ID="synthetic",
            TWITCH_APP_SECRET="synthetic",
            RECORDING_DIRECTORY=str(runtime / "recordings"),
            ARTWORK_BASE_PATH=str(runtime / "recordings/.artwork"),
            LOGS_BASE_DIR=str(runtime / "logs"),
            LOG_DIR=str(runtime / "logs"),
            APP_LOG_DIR=str(runtime / "logs/app"),
            FFMPEG_LOG_DIR=str(runtime / "logs/ffmpeg"),
            STREAMLINK_LOG_DIR=str(runtime / "logs/streamlink"),
        )
        result = asyncio.run(inspect_assets(frontend, arguments.icons_only))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n")
        print(
            json.dumps(
                {
                    key: result[key]
                    for key in ("scope", "mode", "precache_count", "failures")
                }
            )
        )
        assert not result["failures"], result["failures"]


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(ROOT))
    main()

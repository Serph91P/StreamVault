from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.frontend import pwa_router


def _application() -> FastAPI:
    application = FastAPI()
    application.include_router(pwa_router)
    return application


def test_vite_generated_webmanifest_is_served_from_dist(monkeypatch, tmp_path):
    """The TLS app must serve VitePWA's one generated manifest, not public/."""
    manifest_path = tmp_path / "app" / "frontend" / "dist" / "manifest.webmanifest"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        '{"name":"StreamVault","icons":[{"src":"/icon-512x512.png"}]}',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    with TestClient(_application()) as client:
        response = client.get("/manifest.webmanifest")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    assert response.json() == {
        "name": "StreamVault",
        "icons": [{"src": "/icon-512x512.png"}],
    }


def test_missing_vite_generated_webmanifest_is_a_clean_404(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    with TestClient(_application()) as client:
        response = client.get("/manifest.webmanifest")

    assert response.status_code == 404


def test_vite_generated_hashed_workbox_runtime_is_served_from_dist(monkeypatch, tmp_path):
    """The generated SW imports a content-hashed Workbox runtime at the app root."""
    dist_path = tmp_path / "app" / "frontend" / "dist"
    dist_path.mkdir(parents=True)
    runtime = dist_path / "workbox-dcde9eb3.js"
    runtime.write_text("self.workbox = {};", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with TestClient(_application()) as client:
        response = client.get("/workbox-dcde9eb3.js")
        traversal = client.get("/workbox-../../secrets.js")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/javascript")
    assert response.text == "self.workbox = {};"
    assert traversal.status_code == 404

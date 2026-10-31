"""#941: execute both shipped health commands against real HTTPS host policy."""

import os
from pathlib import Path
import socket
import subprocess
import threading
import time

import httpx
import pytest
import uvicorn
import yaml
from fastapi import FastAPI

from app.config.settings import Settings
from app.routes.health import router

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("secure", [True, False])
@pytest.mark.parametrize("source", ["docker", "compose"])
def test_packaged_health_command_obeys_host_policy(monkeypatch, secure, source):
    from app import middleware_all

    base_url = "https://health.example.test" if secure else "http://localhost:7000"
    configuration = Settings(
        _env_file=None,
        BASE_URL=base_url,
        TWITCH_APP_ID="synthetic",
        TWITCH_APP_SECRET="synthetic",
    )
    monkeypatch.setattr(middleware_all, "settings", configuration)
    application = FastAPI()
    application.include_router(router)
    middleware_all.install_http_middleware(application)
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 7000))
    listener.listen()
    server = uvicorn.Server(
        uvicorn.Config(application, log_level="error", lifespan="off")
    )
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [listener]}, daemon=True
    )
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        if source == "docker":
            command = (
                (ROOT / "docker/Dockerfile")
                .read_text()
                .rsplit("\n    CMD ", 1)[1]
                .splitlines()[0]
            )
            arguments = ["/bin/sh", "-c", command]
        else:
            command = yaml.safe_load((ROOT / "docker/docker-compose.yml").read_text())[
                "services"
            ]["app"]["healthcheck"]["test"]
            assert command[0] == "CMD"
            arguments = command[1:]
        result = subprocess.run(
            arguments,
            cwd=ROOT,
            env={
                **os.environ,
                "BASE_URL": base_url,
                "PATH": str(ROOT / ".venv/bin") + os.pathsep + os.environ["PATH"],
            },
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        from app.healthcheck import main

        monkeypatch.setenv("BASE_URL", base_url)
        assert main() == 0
        if secure:
            monkeypatch.setenv("BASE_URL", "https://unrelated.example.test")
            assert main() == 1
        with httpx.Client(trust_env=False) as client:
            assert (
                client.get(
                    "http://127.0.0.1:7000/api/health/live",
                    headers={"Host": "health.example.test"},
                ).status_code
                == 200
            )
            assert client.get(
                "http://127.0.0.1:7000/api/health/live",
                headers={"Host": "unrelated.example.test"},
            ).status_code == (400 if secure else 200)
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        assert not thread.is_alive()


def test_probe_connection_error_is_unhealthy():
    from app.healthcheck import main

    assert main() == 1

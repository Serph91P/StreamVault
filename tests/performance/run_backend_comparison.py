"""Run one isolated no-push image's matched #842 benchmark and retain raw data.

Use the same host, image base/locks, PostgreSQL image, harness and arguments for
both revisions. No published ports or external network; both disposable --rm
containers share the PostgreSQL container's network-none namespace.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid


def command(*args, **kwargs):
    return subprocess.run(
        list(args), check=True, capture_output=True, text=True, **kwargs
    ).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    suffix = uuid.uuid4().hex[:10]
    pg, application = f"sv842-bench-pg-{suffix}", f"sv842-bench-app-{suffix}"
    database = f"streamvault_test_842_bench_{suffix}"
    harness = Path(__file__).resolve().parent
    containers = []
    record = {
        "source_head": args.source_head,
        "image": args.image,
        "pg_image": "postgres:18-alpine",
        "network": "none; app joins only owned PG netns",
        "instrumentation": "byte-identical benchmark-only ingress and SQL driver execute counters",
        "status": "not_finished",
    }
    record["harness_sha256"] = {
        name: hashlib.file_digest((harness / name).open("rb"), "sha256").hexdigest()
        for name in (
            "backend_comparison_entry.py",
            "backend_comparison_client.py",
            "run_backend_comparison.py",
        )
    }
    try:
        command(
            "docker",
            "run",
            "--rm",
            "-d",
            "--name",
            pg,
            "--network",
            "none",
            "--tmpfs",
            "/var/lib/postgresql:rw",
            "-e",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            "-e",
            f"POSTGRES_DB={database}",
            "postgres:18-alpine",
        )
        containers.append(pg)
        deadline = time.monotonic() + 60
        while subprocess.run(
            ["docker", "exec", pg, "pg_isready", "-U", "postgres", "-d", database],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode:
            if time.monotonic() >= deadline:
                raise TimeoutError("own PostgreSQL did not start")
            time.sleep(0.1)
        command(
            "docker",
            "create",
            "--rm",
            "--name",
            application,
            "--network",
            f"container:{pg}",
            "--tmpfs",
            "/recordings:rw,uid=1000,gid=1000",
            "--tmpfs",
            "/app/logs:rw,uid=1000,gid=1000",
            "--tmpfs",
            "/app/config:rw,uid=1000,gid=1000",
            "--tmpfs",
            "/app/data:rw,uid=1000,gid=1000",
            "-e",
            f"DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1/{database}",
            "-e",
            "ENVIRONMENT=test",
            "-e",
            "TWITCH_APP_ID=synthetic-benchmark",
            "-e",
            "TWITCH_APP_SECRET=synthetic-benchmark",
            "-e",
            "BASE_URL=http://127.0.0.1:7000",
            "-e",
            "EVENTSUB_SECRET=benchmark-eventsub-secret",
            "-e",
            "STREAMVAULT_ISOLATED_BENCHMARK=1",
            "-e",
            "RECORDING_DIRECTORY=/recordings",
            "--entrypoint",
            "python",
            args.image,
            "-m",
            "uvicorn",
            "backend_comparison_entry:app",
            "--host",
            "127.0.0.1",
            "--port",
            "7000",
            "--no-access-log",
        )
        containers.append(application)
        for name in ("backend_comparison_entry.py", "backend_comparison_client.py"):
            command(
                "docker",
                "cp",
                str(harness / name),
                f"{application}:/app/{name}",
            )
        started = time.perf_counter()
        command("docker", "start", application)
        deadline = time.monotonic() + 180
        probe = 'import urllib.request; assert urllib.request.urlopen("http://127.0.0.1:7000/api/health/live",timeout=1).status==200'
        while subprocess.run(
            ["docker", "exec", application, "python", "-c", probe],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode:
            if (
                time.monotonic() >= deadline
                or command("docker", "inspect", "-f", "{{.State.Running}}", application)
                != "true"
            ):
                raise TimeoutError(
                    "ordinary application lifespan did not become HTTP-serving"
                )
            time.sleep(0.05)
        record["startup_to_http_seconds"] = time.perf_counter() - started
        # This measures post-startup process RSS, not aggregate peak build memory.
        record["idle_rss_kib"] = int(
            command(
                "docker",
                "exec",
                application,
                "python",
                "-c",
                'from pathlib import Path; print(next(line.split()[1] for line in Path("/proc/1/status").read_text().splitlines() if line.startswith("VmRSS:")))',
            )
        )
        raw = command(
            "docker",
            "exec",
            application,
            "python",
            "/app/backend_comparison_client.py",
        )
        (args.output / "client-stdout.txt").write_text(raw)
        record["workload"] = json.loads(raw.splitlines()[-1])
        record["image_inspect"] = json.loads(
            command("docker", "image", "inspect", args.image)
        )[0]
        record["status"] = "passed"
    except subprocess.CalledProcessError as error:
        (args.output / "failed-command.stdout").write_text(error.stdout or "")
        (args.output / "failed-command.stderr").write_text(error.stderr or "")
        raise
    finally:
        for name in reversed(containers):
            logs = subprocess.run(
                ["docker", "logs", name], capture_output=True, text=True
            )
            (args.output / f"{name}.log").write_text(logs.stdout + logs.stderr)
            subprocess.run(
                ["docker", "stop", "--time", "30", name], capture_output=True, text=True
            )
            # Created-but-not-started --rm containers require explicit removal.
            subprocess.run(["docker", "rm", name], capture_output=True, text=True)
            deadline = time.monotonic() + 5
            while (
                subprocess.run(
                    ["docker", "inspect", name], capture_output=True
                ).returncode
                == 0
            ):
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.05)
        record["cleanup"] = {
            name: subprocess.run(
                ["docker", "inspect", name], capture_output=True
            ).returncode
            != 0
            for name in containers
        }
        (args.output / "result.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n"
        )
    print(
        json.dumps(
            {
                key: value
                for key, value in record.items()
                if key not in {"image_inspect", "workload"}
            }
        )
    )


if __name__ == "__main__":
    main()

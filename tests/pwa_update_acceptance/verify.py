"""Build exact source exports and run original-factory PWA upgrade regressions.

Requires the existing locked .venv/node_modules and local Chromium installation.
Only owned output roots, synthetic fixtures and loopback listeners are used.
"""

import argparse
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
LEGACY = "fa7b19fd089ad51ff27d17243a69fda5b248efee"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    (output / "sources.json").write_text(
        json.dumps({"legacy": LEGACY, "candidate": head}, indent=2)
    )

    def export(revision, name):
        source = output / name
        source.mkdir()
        archive = subprocess.check_output(["git", "archive", revision], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as files:
            files.extractall(source, filter="data")
        frontend = source / "app/frontend"
        (frontend / "node_modules").symlink_to(
            ROOT / "app/frontend/node_modules", target_is_directory=True
        )
        return source

    def build(source, name):
        frontend = source / "app/frontend"
        with (output / (name + ".log")).open("w") as log:
            subprocess.run(
                [
                    "node",
                    "scripts/build-artifact-provenance.mjs",
                    "build",
                    "--mode",
                    "real",
                ],
                cwd=frontend,
                stdout=log,
                stderr=log,
                check=True,
            )
        dist = output / (name + "-dist")
        shutil.copytree(frontend / "dist", dist)
        return dist

    def journey(old, new, name, *options):
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tests/pwa_update_acceptance/run.py"),
                "--old",
                str(old),
                "--new",
                str(new),
                "--output",
                str(output / name),
                *options,
            ],
            cwd=ROOT,
            check=True,
        )

    legacy = export(LEGACY, "legacy-source")
    legacy_dist = build(legacy, "legacy")
    # Restore the archived age of the historical document after rebuilding it.
    # Without Cache-Control, Chromium uses Last-Modified for cache freshness.
    legacy_index = (legacy / "app/frontend/index.html").stat()
    os.utime(
        legacy_dist / "index.html",
        ns=(legacy_index.st_atime_ns, legacy_index.st_mtime_ns),
    )
    candidate = export(head, "candidate-source")
    fixed_dist = build(candidate, "fixed")
    journey(legacy_dist, fixed_dist, "legacy-fixed", "--legacy-source", str(legacy))

    # Supplemental native-401 probe: expose the ORIGINAL ApiClient only in this
    # disposable source export. No registration/auth/HTTP response is replaced.
    entry = candidate / "app/frontend/src/main.ts"
    entry.write_text(
        entry.read_text()
        + "\nimport { ApiClient } from './services/api-real'\n;(window as unknown as { __pwaTestClient: ApiClient }).__pwaTestClient = new ApiClient()\n"
    )
    composition_old = build(candidate, "composition-old")
    marker = candidate / "app/frontend/public/images/pwa-test-generation.svg"
    marker.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><title>synthetic new worker generation</title></svg>'
    )
    composition_new = build(candidate, "composition-new")
    journey(composition_old, composition_new, "fixed-fixed", "--full", "--native-races")
    print(f"PWA original-factory desktop/mobile acceptance passed: {output}")


if __name__ == "__main__":
    main()

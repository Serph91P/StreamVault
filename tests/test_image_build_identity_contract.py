"""Keep immutable Docker identity and its actual build callers in agreement."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
FIELDS = {
    "VERSION": "version",
    "BRANCH": "ref.name",
    "COMMIT_SHA": "revision",
    "BUILD_DATE": "created",
}


def test_runtime_stage_preserves_identity_arguments_and_labels():
    runtime = (ROOT / "docker/Dockerfile").read_text().split(" AS runtime\n", 1)[1]
    for argument, label in FIELDS.items():
        assert f"ARG {argument}=" in runtime
        assert f"STREAMVAULT_{argument}=${{{argument}}}" in runtime
        assert f'org.opencontainers.image.{label}="${{{argument}}}"' in runtime
    assert (
        'org.opencontainers.image.source="https://github.com/Serph91P/StreamVault"'
        in runtime
    )


def test_release_identity_uses_one_timestamp_and_explicit_metadata():
    jobs = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())["jobs"]
    prepare = jobs["prepare"]
    metadata = next(
        step for step in prepare["steps"] if step.get("id") == "docker_meta"
    )
    assert prepare["outputs"]["build_date"] == (
        "${{ fromJSON(steps.docker_meta.outputs.json).labels['org.opencontainers.image.created'] }}"
    )
    assert (
        "org.opencontainers.image.version=${{ steps.version.outputs.version }}"
        in metadata["with"]["labels"]
    )
    assert (
        "org.opencontainers.image.ref.name=${{ github.ref_name }}"
        in metadata["with"]["labels"]
    )
    build = next(
        step
        for step in jobs["build-and-push"]["steps"]
        if step["name"] == "Build Docker image"
    )
    assert (
        "BUILD_DATE=${{ needs.prepare.outputs.build_date }}"
        in build["with"]["build-args"]
    )
    assert "VERSION=${{ needs.prepare.outputs.version }}" in build["with"]["build-args"]
    assert "COMMIT_SHA=${{ github.sha }}" in build["with"]["build-args"]
    assert "BRANCH=${{ github.ref_name }}" in build["with"]["build-args"]


def test_integration_gate_checks_identity_before_and_after_restart():
    workflow = yaml.safe_load((ROOT / ".github/workflows/test.yml").read_text())
    steps = workflow["jobs"]["integration-tests"]["steps"]
    stamp = next(step for step in steps if step.get("id") == "image-identity")
    assert "date -u +%Y-%m-%dT%H:%M:%SZ" in stamp["run"]
    build = next(step for step in steps if step.get("name") == "Build Docker image")
    probe = next(
        step
        for step in steps
        if step.get("name")
        == "Test fresh PostgreSQL migrations, restart, and HTTP surface"
    )
    for argument in FIELDS:
        assert f"{argument}=" in build["with"]["build-args"]
        assert f"STREAMVAULT_EXPECTED_{argument}" in probe["env"]
    assert (
        "BUILD_DATE=${{ steps.image-identity.outputs.build-date }}"
        in build["with"]["build-args"]
    )
    assert (
        probe["env"]["STREAMVAULT_EXPECTED_BUILD_DATE"]
        == "${{ steps.image-identity.outputs.build-date }}"
    )
    smoke = (ROOT / "tests/run_fresh_postgres_proxy_migrations.sh").read_text()
    command = 'python tests/assert_runtime_image_identity.py "${app_container_a}"'
    assert smoke.count(command) == 2
    assert (
        smoke.index(command)
        < smoke.index('docker restart "${app_container_a}"')
        < smoke.rindex(command)
    )

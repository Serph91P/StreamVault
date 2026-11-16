"""Develop validates builds without publishing; complete CI gates stay intact."""

from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def jobs(workflow):
    return yaml.safe_load((ROOT / ".github/workflows" / workflow).read_text())["jobs"]


@pytest.mark.parametrize(
    "name",
    [
        "Log in to GitHub Container Registry",
        "Log in to DockerHub",
        "Push verified Docker images",
    ],
)
def test_develop_skips_every_registry_publication_step(name):
    steps = jobs("release.yml")["build-and-push"]["steps"]
    step = next(step for step in steps if step.get("name") == name)
    # Both main and tag publications retain their original successful-job gate.
    assert step.get("if") == "github.ref != 'refs/heads/develop'"


def test_develop_build_and_security_scan_are_not_skipped():
    build = jobs("release.yml")["build-and-push"]
    assert "if" not in build
    for name in ("Build Docker image", "Run Trivy vulnerability scanner"):
        step = next(step for step in build["steps"] if step.get("name") == name)
        assert "if" not in step
    image = next(
        step for step in build["steps"] if step.get("name") == "Build Docker image"
    )
    assert image["with"]["push"] is False
    assert image["with"]["load"] is True


def test_release_creation_retains_main_and_tags_but_excludes_develop():
    release = jobs("release.yml")["create-release"]
    assert release["if"] == (
        "startsWith(github.ref, 'refs/tags/v') || github.ref == 'refs/heads/main'"
    )
    assert release["needs"] == ["prepare", "build-and-push"]


@pytest.mark.parametrize("workflow", ["release.yml", "docker-build.yml"])
def test_migration_configuration_uses_a_real_isolated_postgres_service(workflow):
    test = jobs(workflow)["test"]
    assert test["timeout-minutes"] == 25
    postgres = test["services"]["postgres"]
    assert postgres["image"] == "postgres:18.6-alpine3.23"
    assert "pg_isready" in postgres["options"]
    assert postgres["ports"] == ["5432:5432"]
    migration = next(
        step for step in test["steps"] if step.get("name") == "Check migrations"
    )
    assert migration["env"]["DATABASE_URL"].startswith("postgresql://")
    assert "localhost:5432/streamvault_ci" in migration["env"]["DATABASE_URL"]
    assert migration["run"] == "uv run python -m app.migrations_init"
    fresh = next(
        step
        for step in test["steps"]
        if step.get("name") == "Run fresh PostgreSQL migration sequence"
    )
    assert (
        "uv run python tests/assert_scoped_migration_postgres.py --all" in fresh["run"]
    )
    assert "createdb -U streamvault_ci streamvault_ci_scoped" in fresh["run"]
    assert fresh["env"]["DATABASE_URL"] == migration["env"]["DATABASE_URL"]
    assert fresh["env"]["SCOPED_MIGRATION_TEST_URL"].endswith("/streamvault_ci_scoped")


def test_full_head_and_base_measurements_have_separate_unweakened_job_limits():
    workflow = jobs("test.yml")
    head = workflow["backend-tests"]
    baseline = workflow["backend-base-coverage"]
    assert head["name"] == "Backend Tests"
    assert head["timeout-minutes"] == baseline["timeout-minutes"] == 25
    assert head["needs"] == ["backend-base-coverage"]
    # A failed prerequisite must not make the required check merely "skipped".
    assert head["if"] == "always()"
    prerequisite = next(
        step
        for step in head["steps"]
        if step.get("name") == "Require successful base measurement"
    )
    assert prerequisite["if"] == "needs.backend-base-coverage.result != 'success'"
    assert "exit 1" in prerequisite["run"]
    measure = next(
        step
        for step in baseline["steps"]
        if step.get("name") == "Measure actual base repository coverage"
    )
    assert measure["env"]["COVERAGE_BASE_SHA"] == (
        "${{ github.event.pull_request.base.sha || github.event.before }}"
    )
    assert 'git archive "$COVERAGE_BASE_SHA"' in measure["run"]
    assert "uv run pytest tests/ -q --cov=app" in measure["run"]
    upload = next(
        step for step in baseline["steps"] if step.get("name") == "Save base coverage"
    )
    assert upload["with"]["path"] == "base-coverage.json"
    assert upload["with"]["if-no-files-found"] == "error"
    download = next(
        step
        for step in head["steps"]
        if step.get("name") == "Read measured base coverage"
    )
    assert download["with"]["name"] == upload["with"]["name"]
    gate = next(
        step
        for step in head["steps"]
        if step.get("name")
        == "Enforce whole new and rewritten module coverage and no repository regression"
    )
    assert "--coverage coverage.json" in gate["run"]
    assert "--baseline base-coverage.json" in gate["run"]
    assert "--inventory docs/architecture/backend-rewrite-inventory.json" in gate["run"]

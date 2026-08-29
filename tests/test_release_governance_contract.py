import re
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
SELECTOR_PATTERN = re.compile(
    r"^\$\{\{ \(github\.ref == '([^']+)' \|\| "
    r"\(startsWith\(github\.ref, '([^']+)'\) && "
    r"!contains\(github\.ref, '([^']+)'\)\)\) && "
    r"'([^']+)' \|\| '([^']+)' \}\}$"
)


def _load_workflow() -> tuple[str, dict]:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    document = yaml.safe_load(text)
    return text, document["jobs"]


def _step(job: dict, name: str) -> dict:
    matches = [step for step in job["steps"] if step.get("name") == name]
    assert len(matches) == 1, f"expected exactly one step named {name!r}"
    return matches[0]


def _selected_environment(selector: str, ref: str) -> str:
    match = SELECTOR_PATTERN.fullmatch(selector)
    assert match, "release environment selector changed unexpectedly"
    main_ref, tag_prefix, development_marker, stable_name, development_name = (
        match.groups()
    )
    is_stable = ref == main_ref or (
        ref.startswith(tag_prefix) and development_marker not in ref
    )
    return stable_name if is_stable else development_name


@pytest.mark.parametrize("job_id", ["build-and-push", "create-release"])
@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("refs/heads/main", "stable-release"),
        ("refs/heads/develop", "development-release"),
        ("refs/tags/v2.13.40", "stable-release"),
        ("refs/tags/v2.13.40-dev", "development-release"),
    ],
)
def test_release_environment_routing(job_id: str, ref: str, expected: str):
    _, jobs = _load_workflow()
    selector = jobs[job_id]["environment"]["name"]
    assert _selected_environment(selector, ref) == expected


def test_image_is_scanned_before_credentials_and_publication():
    _, jobs = _load_workflow()
    build_job = jobs["build-and-push"]
    step_names = [step.get("name") for step in build_job["steps"]]

    required_order = [
        "Build Docker image",
        "Select local image for security scan",
        "Run Trivy vulnerability scanner",
        "Upload Trivy scan results",
        "Log in to GitHub Container Registry",
        "Log in to DockerHub",
        "Push verified Docker images",
    ]
    assert [step_names.index(name) for name in required_order] == sorted(
        step_names.index(name) for name in required_order
    )

    assert "continue-on-error" not in build_job
    for step in build_job["steps"]:
        assert "continue-on-error" not in step

    image_build = _step(build_job, "Build Docker image")
    assert image_build["with"]["platforms"] == "linux/amd64"
    assert image_build["with"]["load"] is True
    assert image_build["with"]["push"] is False
    assert image_build["with"]["tags"] == "${{ needs.prepare.outputs.docker_tags }}"

    selector = _step(build_job, "Select local image for security scan")
    assert selector["env"]["IMAGE_TAGS"] == "${{ needs.prepare.outputs.docker_tags }}"
    assert 'docker image inspect "$SCAN_IMAGE"' in selector["run"]
    assert 'echo "full_ref=$SCAN_IMAGE" >> "$GITHUB_OUTPUT"' in selector["run"]

    trivy = _step(build_job, "Run Trivy vulnerability scanner")
    assert re.fullmatch(r"aquasecurity/trivy-action@[0-9a-f]{40}", trivy["uses"])
    assert trivy["with"]["image-ref"] == "${{ steps.image_name.outputs.full_ref }}"
    assert trivy["with"]["format"] == "sarif"
    assert trivy["with"]["output"] == "trivy-results.sarif"
    assert trivy["with"]["severity"] == "CRITICAL,HIGH"
    assert trivy["with"]["exit-code"] == "1"

    upload = _step(build_job, "Upload Trivy scan results")
    assert upload["if"] == "always() && hashFiles('trivy-results.sarif') != ''"
    assert upload["with"]["sarif_file"] == "trivy-results.sarif"

    push = _step(build_job, "Push verified Docker images")
    assert push["env"]["IMAGE_TAGS"] == "${{ needs.prepare.outputs.docker_tags }}"
    assert 'docker push "$image"' in push["run"]
    assert jobs["create-release"]["needs"] == ["prepare", "build-and-push"]


def test_release_notes_match_the_published_platform():
    workflow, jobs = _load_workflow()
    release_job = jobs["create-release"]
    release_job_text = yaml.safe_dump(release_job)

    assert "multi-architecture" not in workflow
    assert "linux/amd64, linux/arm64" not in workflow
    assert "linux/amd64 Docker image" in release_job_text
    assert "| Architectures | linux/amd64 |" in release_job_text

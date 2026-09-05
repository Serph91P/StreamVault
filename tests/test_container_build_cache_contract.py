from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_STEPS = [
    (
        ".github/workflows/docker-build.yml",
        "build",
        "Build Docker image (validation only)",
    ),
    (".github/workflows/test.yml", "integration-tests", "Build Docker image"),
    (".github/workflows/release.yml", "build-and-push", "Build Docker image"),
]


@pytest.mark.parametrize(("workflow_path", "job_name", "step_name"), BUILD_STEPS)
def test_container_build_cache_bypasses_base_and_runtime_layers(
    workflow_path: str, job_name: str, step_name: str
):
    workflow = yaml.safe_load((REPO_ROOT / workflow_path).read_text(encoding="utf-8"))
    steps = workflow["jobs"][job_name]["steps"]
    matches = [step for step in steps if step.get("name") == step_name]

    assert len(matches) == 1, f"expected exactly one step named {step_name!r}"
    cache_settings = matches[0]["with"]
    assert cache_settings["cache-from"] == "type=gha"
    assert cache_settings["cache-to"] == "type=gha,mode=max"
    assert cache_settings["no-cache-filters"] == "base,runtime"

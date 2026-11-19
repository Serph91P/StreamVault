"""Real PWA browser acceptance is a required frontend aggregate dependency."""

from pathlib import Path

import yaml


def test_original_factory_pwa_journeys_are_gated_in_ci():
    workflow = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / ".github/workflows/test.yml").read_text()
    )
    jobs = workflow["jobs"]
    assert jobs["frontend-build"]["needs"] == ["frontend-core", "frontend-browser"]
    assert jobs["frontend-build"]["if"] == "always()"
    assert "pwa-update-regressions" in jobs["frontend-browser"]["needs"]
    assert "if" not in jobs["frontend-browser"]
    assert (
        'test "${{ needs.frontend-browser.result }}" = success'
        in jobs["frontend-build"]["steps"][0]["run"]
    )
    job = jobs["pwa-update-regressions"]
    assert job["timeout-minutes"] == 12
    run = "\n".join(step.get("run", "") for step in job["steps"])
    assert "uv sync --locked --all-groups" in run
    assert "tests/pwa_update_acceptance/verify.py" in run
    assert "continue-on-error" not in job
    assert all("continue-on-error" not in step for step in job["steps"])

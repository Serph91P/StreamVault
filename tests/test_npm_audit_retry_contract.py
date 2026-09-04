import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "ci" / "npm-audit-with-retry.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "test.yml"


@pytest.fixture
def fake_commands(tmp_path: Path) -> tuple[Path, Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    invocation_log = tmp_path / "npm-invocations"
    sleep_log = tmp_path / "sleep-invocations"

    npm = bin_dir / "npm"
    npm.write_text(
        """#!/usr/bin/env bash
set -u
printf '%s\\n' "$*" >> "$NPM_INVOCATION_LOG"
attempt=$(wc -l < "$NPM_INVOCATION_LOG")

case "$NPM_TEST_SCENARIO" in
  transient-then-success)
    if [[ "$attempt" -eq 1 ]]; then
      printf '%s\\n' \
        'npm error code E503' \
        'npm error 503 Service Unavailable - POST https://token:secret@registry.npmjs.org/-/npm/v1/security/audits/quick' >&2
      exit 1
    fi
    printf '%s\\n' 'found 0 vulnerabilities'
    ;;
  vulnerability)
    printf '%s\\n' \
      '# npm audit report' \
      'example-package  <1.2.3' \
      '1 high severity vulnerability'
    exit 1
    ;;
  transient)
    printf '%s\\n' \
      'npm error code E503' \
      'npm error 503 Service Unavailable - POST https://registry.npmjs.org/-/npm/v1/security/audits/quick' >&2
    exit 1
    ;;
  malformed)
    printf '%s\\n' 'unexpected audit response' >&2
    exit 1
    ;;
  *)
    printf '%s\\n' "unknown test scenario: $NPM_TEST_SCENARIO" >&2
    exit 2
    ;;
esac
""",
        encoding="utf-8",
    )
    npm.chmod(0o755)

    sleep = bin_dir / "sleep"
    sleep.write_text(
        """#!/usr/bin/env bash
set -u
printf '%s\\n' "$*" >> "$SLEEP_INVOCATION_LOG"
""",
        encoding="utf-8",
    )
    sleep.chmod(0o755)
    return bin_dir, invocation_log, sleep_log


def _run_helper(
    fake_commands: tuple[Path, Path, Path], scenario: str
) -> tuple[subprocess.CompletedProcess[str], list[str], list[str]]:
    bin_dir, invocation_log, sleep_log = fake_commands
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
            "NPM_INVOCATION_LOG": str(invocation_log),
            "NPM_TEST_SCENARIO": scenario,
            "SLEEP_INVOCATION_LOG": str(sleep_log),
        }
    )
    result = subprocess.run(
        ["bash", str(HELPER)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    invocations = (
        invocation_log.read_text(encoding="utf-8").splitlines()
        if invocation_log.exists()
        else []
    )
    sleeps = (
        sleep_log.read_text(encoding="utf-8").splitlines() if sleep_log.exists() else []
    )
    return result, invocations, sleeps


def test_transient_503_is_retried_then_succeeds(fake_commands):
    result, invocations, sleeps = _run_helper(fake_commands, "transient-then-success")

    assert result.returncode == 0
    assert invocations == ["audit --audit-level high"] * 2
    assert sleeps == ["2"]
    assert "token:secret" not in result.stdout + result.stderr


def test_vulnerability_fails_immediately_without_retry(fake_commands):
    result, invocations, sleeps = _run_helper(fake_commands, "vulnerability")

    assert result.returncode != 0
    assert invocations == ["audit --audit-level high"]
    assert sleeps == []


def test_exhausted_transient_failure_is_nonzero_and_bounded(fake_commands):
    result, invocations, sleeps = _run_helper(fake_commands, "transient")

    assert result.returncode != 0
    assert invocations == ["audit --audit-level high"] * 3
    assert sleeps == ["2", "2"]


def test_malformed_output_fails_closed_without_retry(fake_commands):
    result, invocations, sleeps = _run_helper(fake_commands, "malformed")

    assert result.returncode != 0
    assert invocations == ["audit --audit-level high"]
    assert sleeps == []


def test_workflow_uses_retry_helper_instead_of_direct_npm_audit():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "bash ../../scripts/ci/npm-audit-with-retry.sh" in workflow
    assert "npm audit --audit-level high" not in workflow

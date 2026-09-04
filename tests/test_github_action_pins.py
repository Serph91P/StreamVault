"""Contract tests for immutable GitHub Actions references."""

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
USES_KEY = re.compile(r"^\s*(?:-\s*)?uses\s*:")
USES_LINE = re.compile(
    r"^\s*(?:-\s*)?uses\s*:\s*"
    r"(?P<reference>[^\s#]+)"
    r"(?:\s+#\s*(?P<comment>.*))?\s*$"
)
EXTERNAL_ACTION = re.compile(
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
    r"(?:/[A-Za-z0-9_.-]+)*@[0-9a-f]{40}"
)
VERSION_COMMENT = re.compile(r"v[0-9][0-9A-Za-z._+-]*")


def test_external_github_actions_are_pinned_to_commits():
    workflows = sorted([*WORKFLOWS_DIR.glob("*.yml"), *WORKFLOWS_DIR.glob("*.yaml")])
    assert workflows, f"no workflow YAML files found in {WORKFLOWS_DIR}"

    external_references = []
    errors = []
    for workflow in workflows:
        for line_number, line in enumerate(
            workflow.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not USES_KEY.match(line):
                continue

            location = f"{workflow.relative_to(REPO_ROOT)}:{line_number}"
            match = USES_LINE.fullmatch(line)
            if not match:
                errors.append(f"{location}: malformed uses reference: {line.strip()}")
                continue

            reference = match.group("reference")
            if reference.startswith("./"):
                continue

            external_references.append(reference)
            if not EXTERNAL_ACTION.fullmatch(reference):
                errors.append(
                    f"{location}: external action must use a full 40-character "
                    f"lowercase commit SHA: {reference}"
                )
            if not VERSION_COMMENT.fullmatch(match.group("comment") or ""):
                errors.append(
                    f"{location}: external action must have an inline # v... "
                    f"version comment: {reference}"
                )

    assert external_references, "no external GitHub Actions references found"
    assert not errors, "\n" + "\n".join(errors)

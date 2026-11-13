"""The coverage gate must use executable statement+branch counts, not rounding."""

import json
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

SCRIPT = Path(__file__).with_name("check_backend_coverage.py")


def assert_inventory_is_strict(config):
    root = SCRIPT.parent.parent
    inventory = json.loads(
        (root / "docs/architecture/backend-rewrite-inventory.json").read_text()
    )["modules"]
    for path in inventory:
        assert path in config["files"], f"Not checked by CI mypy: {path}"
        module = path.removesuffix(".py").replace("/", ".").removesuffix(".__init__")
        effective = dict(config)
        for override in config.get("overrides", []):
            if module in override["module"]:
                effective.update(override)
        for flag in (
            "disallow_untyped_defs",
            "disallow_untyped_calls",
            "disallow_any_generics",
        ):
            assert effective.get(flag) is True, f"Not strict: {module}/{flag}"


def test_complete_rewrite_inventory_is_in_the_strict_ci_gate():
    config = tomllib.loads((SCRIPT.parent.parent / "pyproject.toml").read_text())
    assert_inventory_is_strict(config["tool"]["mypy"])


def summary(covered, total):
    return {
        "covered_lines": covered,
        "num_statements": total,
        "covered_branches": 0,
        "num_branches": 0,
    }


def run_gate(tmp_path, final, baseline, modules):
    paths = []
    for name, data in [
        ("final.json", final),
        ("baseline.json", baseline),
        ("scope.json", {"modules": modules}),
    ]:
        path = tmp_path / name
        path.write_text(json.dumps(data))
        paths.append(str(path))
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--coverage",
            paths[0],
            "--baseline",
            paths[1],
            "--inventory",
            paths[2],
        ],
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("covered,expected", [(85, 0), (84, 1), (100, 0)])
async def test_rewritten_module_has_unweakened_85_percent_threshold(
    tmp_path, covered, expected
):
    final = {
        "totals": summary(90, 100),
        "files": {"app/rewrite.py": {"summary": summary(covered, 100)}},
    }
    result = run_gate(tmp_path, final, {"totals": summary(60, 100)}, ["app/rewrite.py"])
    assert result.returncode == expected, result.stdout + result.stderr


async def test_gate_checks_repository_even_when_every_module_passes(tmp_path):
    final = {
        "totals": summary(89, 100),
        "files": {"app/rewrite.py": {"summary": summary(100, 100)}},
    }
    result = run_gate(tmp_path, final, {"totals": summary(90, 100)}, ["app/rewrite.py"])
    assert result.returncode == 1
    assert "repository regressed" in result.stdout


async def test_gate_counts_branches_and_never_rounds_up(tmp_path):
    item = {
        "summary": {
            **summary(85, 100),
            "covered_branches": 84,
            "num_branches": 100,
            "percent_covered": 85,
        }
    }
    final = {"totals": summary(100, 100), "files": {"app/rewrite.py": item}}
    result = run_gate(tmp_path, final, {"totals": summary(1, 2)}, ["app/rewrite.py"])
    assert result.returncode == 1
    assert "169/200" in result.stdout


async def test_gate_fails_closed_for_unmeasured_modules(tmp_path):
    result = run_gate(
        tmp_path,
        {"totals": summary(100, 100), "files": {}},
        {"totals": summary(1, 2)},
        ["app/missing.py"],
    )
    assert result.returncode == 1
    assert "missing coverage" in result.stdout


async def test_empty_python_package_has_no_executable_denominator(tmp_path):
    result = run_gate(
        tmp_path,
        {
            "totals": summary(100, 100),
            "files": {"app/__init__.py": {"summary": summary(0, 0)}},
        },
        {"totals": summary(1, 2)},
        ["app/__init__.py"],
    )
    assert result.returncode == 0, result.stdout + result.stderr

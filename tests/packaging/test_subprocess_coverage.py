"""Exercise pytest-cov's real child-process measurement with the project config."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib


def test_pytest_cov_measures_child_only_branches(tmp_path: Path) -> None:
    project = Path(__file__).resolve().parents[2] / "pyproject.toml"
    run = tomllib.loads(project.read_text())["tool"]["coverage"]["run"]
    config = tmp_path / "pyproject.toml"
    config.write_text(
        '[tool.coverage.run]\nbranch = true\nsource = ["child_only"]\n'
        f"patch = {json.dumps(run.get('patch', []))}\n"
    )
    (tmp_path / "child_only.py").write_text(
        "def answer(positive):\n    if positive:\n        return 42\n    return 0\n"
    )
    (tmp_path / "test_child.py").write_text(
        "import subprocess, sys\n"
        "def test_child():\n"
        "    subprocess.run([sys.executable, '-c', "
        "'import child_only; assert child_only.answer(True) == 42'], check=True)\n"
    )
    env = dict(os.environ, COVERAGE_FILE=str(tmp_path / ".coverage"))
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "test_child.py",
            "-q",
            "--cov=child_only",
            f"--cov-config={config}",
            "--cov-report=json:coverage.json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (tmp_path / "coverage.json").is_file(), completed.stdout + completed.stderr
    report = json.loads((tmp_path / "coverage.json").read_text())
    child = report["files"]["child_only.py"]
    assert child["executed_lines"] == [1, 2, 3]
    assert child["missing_lines"] == [4]
    assert child["executed_branches"] == [[2, 3]]
    assert child["missing_branches"] == [[2, 4]]

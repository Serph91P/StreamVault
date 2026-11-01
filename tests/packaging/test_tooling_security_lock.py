"""Tooling lock coverage is separate from the production pip-audit export."""

from pathlib import Path
import tomllib

from packaging.version import Version


ROOT = Path(__file__).resolve().parents[2]


def test_filelock_tooling_lock_excludes_the_three_fixed_advisory_ranges():
    # GHSA-v4x8-3wr5-3wq8, GHSA-567q-5qvw-pf92, GHSA-9vhv-jxww-xfm5.
    packages = tomllib.loads((ROOT / "uv.lock").read_text())["package"]
    versions = [
        package["version"] for package in packages if package["name"] == "filelock"
    ]
    assert versions
    assert all(Version(version) >= Version("4.2.1") for version in versions)
    minimum_tooling_fixes = {"virtualenv": "21.14.10", "msgpack": "1.2.3"}
    for name, minimum in minimum_tooling_fixes.items():
        selected = [
            package["version"] for package in packages if package["name"] == name
        ]
        assert selected and all(
            Version(version) >= Version(minimum) for version in selected
        )
    production = {
        line.split("==", 1)[0].strip().lower()
        for line in (ROOT / "requirements.txt").read_text().splitlines()
        if line and not line.startswith(("#", " "))
    }
    assert not {"filelock", "virtualenv", "python-discovery", "pre-commit"} & production

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "docker" / "Dockerfile"


def _instructions(dockerfile: str) -> list[tuple[str, str]]:
    instructions: list[tuple[str, str]] = []
    pending = ""

    for raw_line in dockerfile.splitlines():
        line = raw_line.strip()
        if not pending and (not line or line.startswith("#")):
            continue

        pending = f"{pending} {line}".strip()
        if pending.endswith("\\"):
            pending = pending[:-1].rstrip()
            continue

        keyword, separator, value = pending.partition(" ")
        assert separator, f"Invalid Dockerfile instruction: {pending}"
        instructions.append((keyword.upper(), " ".join(value.split())))
        pending = ""

    assert not pending, "Unterminated Dockerfile continuation"
    return instructions


def _runtime_instructions(dockerfile: str) -> list[tuple[str, str]]:
    runtime: list[tuple[str, str]] = []
    in_runtime = False

    for keyword, value in _instructions(dockerfile):
        if keyword == "FROM":
            if in_runtime:
                break
            in_runtime = value.lower().endswith(" as runtime")
            continue
        if in_runtime:
            runtime.append((keyword, value))

    assert in_runtime, "Runtime stage not found"
    return runtime


def _validate_runtime_contract(dockerfile: str) -> None:
    runtime = _runtime_instructions(dockerfile)

    copy_packages = (
        "--from=python-deps /usr/local/lib/python3.14/site-packages "
        "/usr/local/lib/python3.14/site-packages"
    )
    remove_pip = "python -m pip uninstall --yes pip"
    normalize_permissions = (
        "chmod -R a+rX /bin /lib /usr/bin /usr/lib /usr/sbin /usr/share "
        "/usr/local/bin /usr/local/lib/python3.14/site-packages"
    )

    copy_index = runtime.index(("COPY", copy_packages))
    cleanup_indices = [
        index
        for index, (keyword, value) in enumerate(runtime)
        if keyword == "RUN" and remove_pip in value and normalize_permissions in value
    ]
    assert len(cleanup_indices) == 1
    cleanup_index = cleanup_indices[0]

    user_instructions = [
        (index, value)
        for index, (keyword, value) in enumerate(runtime)
        if keyword == "USER"
    ]
    assert user_instructions
    final_user_index, final_user = user_instructions[-1]
    assert final_user == "appuser"

    assert copy_index < cleanup_index < final_user_index
    assert all("setuptools==" not in value for _, value in runtime)
    assert all("msgpack==" not in value for _, value in runtime)


def test_runtime_image_removes_pip_and_normalizes_public_runtime_paths():
    _validate_runtime_contract(DOCKERFILE.read_text(encoding="utf-8"))


def test_contract_rejects_commented_out_runtime_cleanup():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    active = (
        "RUN python -m pip uninstall --yes pip && \\\n"
        "    chmod -R a+rX /bin /lib /usr/bin /usr/lib /usr/sbin /usr/share "
        "/usr/local/bin /usr/local/lib/python3.14/site-packages"
    )
    commented = "\n".join(f"# {line}" for line in active.splitlines())
    assert active in dockerfile

    with pytest.raises(AssertionError):
        _validate_runtime_contract(dockerfile.replace(active, commented, 1))


def test_contract_rejects_later_root_user_override():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    marker = "USER appuser\nWORKDIR /app"
    assert marker in dockerfile

    with pytest.raises(AssertionError):
        _validate_runtime_contract(
            dockerfile.replace(marker, "USER appuser\nUSER root\nWORKDIR /app", 1)
        )

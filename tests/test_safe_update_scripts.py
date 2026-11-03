"""Run disposable helper copies with a closed PATH: never reach a real daemon/API."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
IDLE = dict(
    has_active_recordings=False,
    active_count=0,
    safe_to_update=True,
    active_streamers=[],
    message="idle",
    timestamp="2026-10-31T00:00:00Z",
)
ACTIVE = dict(
    IDLE,
    has_active_recordings=True,
    active_count=1,
    safe_to_update=False,
    active_streamers=["synthetic"],
)


@pytest.fixture
def sandbox(tmp_path):
    root = tmp_path / "install with spaces"
    (root / "scripts").mkdir(parents=True)
    (root / "docker").mkdir()
    shutil.copy2(ROOT / "docker/docker-compose.yml", root / "docker/docker-compose.yml")
    for name in ("check_safe_to_update.sh", "safe_docker_update.sh"):
        shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("bash", "dirname", "date", "grep", "tr"):
        (bin_dir / name).symlink_to(shutil.which(name))
    commands = {
        "curl": """printf '%s\\n' "$*" >> "$CURL_LOG"
while IFS= read -r header; do printf '%s\\n' "$header" >> "$CURL_LOG"; done
if [[ ${CURL_EXIT:-0} != 0 ]]; then exit "$CURL_EXIT"; fi
if [[ -e $CURL_LOG.seen ]]; then printf '%s' "${SECOND_RESPONSE-$RESPONSE}"; else printf '%s' "$RESPONSE"; fi
: > "$CURL_LOG.seen"
if [[ $* == *--write-out* ]]; then printf '\\n%s' "${HTTP_STATUS:-200}"; fi
""",
        "docker": """printf '%s|%s\\n' "$PWD" "$*" >> "$DOCKER_LOG"
case "$*" in
  *version) exit "${COMPOSE_VERSION_EXIT:-0}";;
  *"ps -q app") printf 'synthetic-container\\n';;
  "inspect --format "*) printf '%s\\n' "${HEALTH-healthy}";;
  *ps) printf 'app Up\\n';;
esac
exit "${DOCKER_EXIT:-0}"
""",
        "sleep": 'exit "${SLEEP_EXIT:-0}"\n',
    }
    for name, body in commands.items():
        path = bin_dir / name
        path.write_text("#!/bin/bash\n" + body)
        path.chmod(0o755)
    env = dict(
        PATH=str(bin_dir),
        RESPONSE=json.dumps(IDLE),
        CURL_LOG=str(tmp_path / "curl.log"),
        DOCKER_LOG=str(tmp_path / "docker.log"),
        STREAMVAULT_API_KEY="synthetic-test-key",
        HOME=str(tmp_path),
    )
    return root, bin_dir, env, tmp_path


def run(
    sandbox,
    parser="jq",
    update=False,
    args=(),
    response=None,
    stdin="no\n",
    direct=False,
    **env_changes,
):
    root, bin_dir, env, cwd = sandbox
    if parser == "jq":
        (bin_dir / "jq").symlink_to(shutil.which("jq"), target_is_directory=False)
    elif parser == "python":
        (bin_dir / "python3").symlink_to(sys.executable)
    env = dict(env, **env_changes)
    if response is not None:
        env["RESPONSE"] = response
    script = (
        root
        / "scripts"
        / ("safe_docker_update.sh" if update else "check_safe_to_update.sh")
    )
    result = subprocess.run(
        ([str(script)] if direct else ["/bin/bash", str(script)]) + list(args),
        cwd=cwd,
        env=env,
        input=stdin,
        text=True,
        capture_output=True,
        timeout=5,
    )
    docker = Path(env["DOCKER_LOG"])
    mutations = (
        [
            line
            for line in docker.read_text().splitlines()
            if any(
                word in line.split("|")[1].split()
                for word in ("pull", "down", "up", "restart")
            )
        ]
        if docker.exists()
        else []
    )
    return result, mutations


@pytest.mark.parametrize("code", ["301", "307", "401", "403", "500", "503"])
def test_only_http_200_can_authorize_update(sandbox, code):
    result, mutations = run(sandbox, update=True, HTTP_STATUS=code)
    assert result.returncode == 2, result.stdout + result.stderr
    assert not mutations


@pytest.mark.parametrize("parser", ["jq", "python"])
def test_integral_json_number_has_parser_parity(sandbox, parser):
    result, _ = run(
        sandbox, parser=parser, response=json.dumps(dict(IDLE, active_count=0.0))
    )
    assert result.returncode == 0, result.stdout + result.stderr


BAD = [
    "",
    "not json",
    "null",
    "[]",
    "{}",
    json.dumps(dict(IDLE, safe_to_update="true")),
    json.dumps(dict(IDLE, active_count="0")),
    json.dumps(dict(IDLE, active_count=False)),
    json.dumps(dict(IDLE, active_count=-1)),
    json.dumps(dict(ACTIVE, active_count=float("inf"))),
    json.dumps(ACTIVE).replace('"active_count": 1', '"active_count": 1e309'),
    json.dumps(dict(IDLE, active_count=1)),
    json.dumps(dict(IDLE, has_active_recordings=True)),
    json.dumps(dict(IDLE, active_streamers="oops")),
    json.dumps(dict(IDLE, safe_to_update=False)),
    json.dumps(IDLE) + "\n" + json.dumps(IDLE),
]
BAD += [
    json.dumps({k: v for k, v in IDLE.items() if k != field})
    for field in (
        "safe_to_update",
        "active_count",
        "has_active_recordings",
        "active_streamers",
    )
]


@pytest.mark.parametrize("parser", ["jq", "python"])
@pytest.mark.parametrize("update", [False, True])
@pytest.mark.parametrize(
    "response,expected",
    [(json.dumps(IDLE), 0), (json.dumps(ACTIVE), 1)] + [(v, 2) for v in BAD],
)
def test_status_is_validated_before_any_update(
    sandbox, parser, update, response, expected
):
    result, mutations = run(
        sandbox,
        parser,
        update,
        ("--max-wait-minutes", "1" if expected == 2 else "0"),
        response,
        direct=True,
        SLEEP_EXIT="99",
    )
    assert result.returncode == expected, result.stdout + result.stderr
    assert bool(mutations) == (update and expected == 0)
    if expected == 2:
        assert "Waiting:" not in result.stdout


@pytest.mark.parametrize("parser", ["jq", "python"])
@pytest.mark.parametrize("code", [7, 22, 28])
@pytest.mark.parametrize("update", [False, True])
def test_network_and_http_failures_are_errors(sandbox, parser, code, update):
    result, mutations = run(sandbox, parser, update, CURL_EXIT=str(code))
    assert result.returncode == 2, result.stdout + result.stderr
    assert not mutations


@pytest.mark.parametrize("state", ["missing", "not-executable"])
def test_missing_guard_cannot_be_skipped(sandbox, state):
    helper = sandbox[0] / "scripts/check_safe_to_update.sh"
    if state == "missing":
        helper.unlink()
    else:
        helper.chmod(0o644)
    result, mutations = run(sandbox, update=True)
    assert result.returncode == 2, result.stdout + result.stderr
    assert not mutations


@pytest.mark.parametrize(
    "args",
    [
        ("--max-wait-minutes",),
        ("--max-wait-minutes", "-1"),
        ("--max-wait-minutes", "x"),
        ("--max-wait-minutes", "1+1"),
        ("--max-wait-minutes", "99999999999999999999999999999"),
        ("--unknown",),
    ],
)
@pytest.mark.parametrize("update", [False, True])
def test_invalid_arguments_are_errors(sandbox, args, update):
    result, mutations = run(sandbox, update=update, args=args)
    assert result.returncode == 2, result.stdout + result.stderr
    assert not mutations


@pytest.mark.parametrize("command", ["curl", "docker", "parsers"])
def test_missing_required_command_is_closed(sandbox, command):
    if command != "parsers":
        (sandbox[1] / command).unlink()
    result, mutations = run(
        sandbox, parser="none" if command == "parsers" else "jq", update=True
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert not mutations


def test_default_layout_and_auth_request(sandbox):
    result, mutations = run(sandbox, update=True, direct=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(mutations) == 3
    for line in mutations:
        assert line.startswith(str(sandbox[0] / "docker") + "|")
        assert "-f " + str(sandbox[0] / "docker/docker-compose.yml") in line
    curl = Path(sandbox[2]["CURL_LOG"]).read_text()
    assert "http://localhost:7000/api/status/recordings-active" in curl
    assert "Accept: application/json" in curl
    assert "X-API-Key: synthetic-test-key" in curl
    assert "--connect-timeout" in curl and "--max-time" in curl
    assert "--location" not in curl


def test_scripts_are_executable_and_valid_bash():
    for name in ("check_safe_to_update.sh", "safe_docker_update.sh"):
        path = ROOT / "scripts" / name
        assert os.access(path, os.X_OK)
        assert subprocess.run(["/bin/bash", "-n", str(path)]).returncode == 0


@pytest.mark.parametrize("health", ["unhealthy", "starting", "", "running"])
def test_unhealthy_restart_is_not_reported_as_success(sandbox, health):
    result, _ = run(sandbox, update=True, HEALTH=health)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Update completed successfully" not in result.stdout


@pytest.mark.parametrize("parser", ["jq", "python"])
@pytest.mark.parametrize("next_response,expected", [(json.dumps(IDLE), 0), ("{}", 2)])
def test_wait_rechecks_status(sandbox, parser, next_response, expected):
    result, mutations = run(
        sandbox,
        parser,
        update=True,
        response=json.dumps(ACTIVE),
        SECOND_RESPONSE=next_response,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    assert bool(mutations) == (expected == 0)


def test_interrupted_wait_is_error(sandbox):
    result, mutations = run(
        sandbox, update=True, response=json.dumps(ACTIVE), SLEEP_EXIT="1"
    )
    assert result.returncode == 2
    assert not mutations


@pytest.mark.parametrize(
    "stdin,updates", [("yes\n", True), ("no\n", False), ("", False)]
)
def test_force_requires_explicit_confirmation(sandbox, stdin, updates):
    (sandbox[0] / "scripts/check_safe_to_update.sh").unlink()
    result, mutations = run(sandbox, update=True, args=("--force",), stdin=stdin)
    assert result.returncode == 0, result.stdout + result.stderr
    assert bool(mutations) == updates
    assert not Path(sandbox[2]["CURL_LOG"]).exists()


@pytest.mark.parametrize("command", ["jq", "python3"])
def test_broken_parser_is_error(sandbox, command):
    path = sandbox[1] / command
    path.write_text("#!/bin/bash\nexit 1\n")
    path.chmod(0o755)
    result, mutations = run(sandbox, parser="none", update=True)
    assert result.returncode == 2
    assert not mutations


def test_python_optimization_cannot_disable_validation(sandbox):
    result, mutations = run(
        sandbox,
        parser="python",
        update=True,
        response=json.dumps(dict(IDLE, safe_to_update=False)),
        PYTHONOPTIMIZE="1",
    )
    assert result.returncode == 2
    assert not mutations


@pytest.mark.parametrize("key", ["", "synthetic\nInjected: value"])
def test_missing_or_invalid_credential_is_error(sandbox, key):
    result, mutations = run(sandbox, update=True, STREAMVAULT_API_KEY=key)
    assert result.returncode == 2
    assert not mutations


def test_custom_api_url(sandbox):
    result, _ = run(sandbox, STREAMVAULT_API_URL="https://synthetic.invalid:7443/")
    assert result.returncode == 0
    assert (
        "https://synthetic.invalid:7443/api/status/recordings-active"
        in Path(sandbox[2]["CURL_LOG"]).read_text()
    )


def test_legacy_compose_fallback(sandbox):
    (sandbox[1] / "docker-compose").symlink_to(sandbox[1] / "docker")
    result, mutations = run(sandbox, update=True, COMPOSE_VERSION_EXIT="1")
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(mutations) == 3


def test_no_compose_is_error(sandbox):
    result, mutations = run(sandbox, update=True, COMPOSE_VERSION_EXIT="1")
    assert result.returncode == 2
    assert not mutations


def test_missing_compose_file_is_error(sandbox):
    (sandbox[0] / "docker/docker-compose.yml").unlink()
    result, mutations = run(sandbox, update=True)
    assert result.returncode == 2
    assert not mutations


def test_pull_failure_stops_later_update_steps(sandbox):
    result, mutations = run(sandbox, update=True, DOCKER_EXIT="1")
    assert result.returncode == 2
    assert len(mutations) == 1 and mutations[0].endswith("pull")

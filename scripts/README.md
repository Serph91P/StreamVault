# StreamVault safe-update helpers

These Bash helpers wait for recordings to finish before updating the supplied
Compose installation. They do not provide zero downtime or prevent a new recording
from starting between the status check and shutdown. Schedule maintenance accordingly.

## Installation layout and configuration

Keep the repository layout intact:

```text
streamvault/
  scripts/check_safe_to_update.sh
  scripts/safe_docker_update.sh
  docker/docker-compose.yml
```

The update helper resolves paths from its own location, changes to `docker/`, and
passes the absolute `docker/docker-compose.yml` to every Compose invocation. This
preserves Compose's `docker/`-relative mounts and project identity even when invoked
from another working directory. It does not discover another stack or a root Compose
file. Configure the supplied Compose installation normally; the helpers never source
an environment file. Compose itself loads its normal configuration from `docker/`.

Requirements: Bash, curl (supporting `--header @-`), jq **or** Python 3, Docker CLI
and either Docker Compose v2 or legacy `docker-compose`. The scripts are executable
in Git. If an installation stripped their modes, restore both before running:

```bash
chmod +x scripts/check_safe_to_update.sh scripts/safe_docker_update.sh
```

Export these in the process that runs the helper (do not put a key in command-line
arguments, logs, or source control):

- `STREAMVAULT_API_KEY`: an **existing**, active StreamVault API key belonging to
  an authorized active user. The key is sent as `X-API-Key` to the read-only status
  endpoint, not used to grant update/admin rights. Docker access is separate.
- `STREAMVAULT_API_URL`: default `http://localhost:7000`, matching the supplied
  `7000:7000` port mapping. For a custom host/port or reverse proxy, use the direct
  StreamVault origin (HTTPS for remote access). It must point to the **same instance**
  as the Compose installation being updated. No URL or credential discovery occurs.

The protected `GET /api/status/recordings-active` request uses `Accept:
application/json`. Missing credentials, HTTP 401/403/5xx, login/setup redirects,
network failures, and invalid responses abort the check. Requests have a 5-second
connection timeout and a 15-second total timeout; redirects are not followed.
Only HTTP 200 and consistent, correctly typed `safe_to_update`,
`has_active_recordings`, `active_count` and `active_streamers` fields are accepted.
Both parsers enforce the same decision: idle means `true`, `false`, `0`, and `[]`.

## Check only

From the repository root, with the environment above already configured:

```bash
./scripts/check_safe_to_update.sh
./scripts/check_safe_to_update.sh --wait --max-wait-minutes 30
```

- `0`: verified idle.
- `1`: verified active, or waiting deadline reached.
- `2`: unknown/error (including missing commands, invalid arguments or auth failure).

`--wait` polls every 60 seconds, shortening the last sleep to the remaining wait.
The default wait budget is 60 minutes. `--max-wait-minutes` accepts 0 through
999999999 (at most nine decimal digits, including leading zeros); zero checks once
without waiting. Elapsed time is monotonic Bash time; an in-flight request can take
up to its request timeout. Unknown status aborts immediately rather than being retried.

## Protected update

```bash
./scripts/safe_docker_update.sh --max-wait-minutes 30
# Absolute invocation from any directory works too:
/path/to/streamvault/scripts/safe_docker_update.sh
```

The helper requires a successful recording check **before** `pull`, `down`, and
`up -d`. Missing or non-executable checkers are fatal, never silently skipped.
A guard result of `1` is preserved; all other failures produce `2`.
After starting, it resolves the `app` container and inspects its configured health
check (the supplied Compose file probes `/api/health/live` on port 7000).
It waits up to 24 polls, five seconds apart, for `healthy`; missing/unhealthy status,
inspection/start failures, and timeout return `2`, never a success message.
Exit `0` means the app healthcheck passed, not that media/provider workflows were
exercised. The helper does not roll back a partially completed update.

### Explicit emergency bypass

```bash
./scripts/safe_docker_update.sh --force
```

This existing emergency path can interrupt recordings. It bypasses the guard **only**
after the operator types exactly `yes`; rejection or EOF cancels without updating
(exit `0`). Do not use it for normal automation or to hide an unknown status.

## Local regression checks (no daemon or real API)

```bash
uv run pytest tests/test_safe_update_scripts.py -v
bash -n scripts/check_safe_to_update.sh scripts/safe_docker_update.sh
```

Tests execute disposable layout copies with a closed command PATH and synthetic
credentials. Docker, curl and sleep are harmless shell stubs; jq/Python parser paths
run real parsers. No actual stack update, daemon restart or operator credentials are
needed. A real deployment/restart health acceptance is a separate authorized step.

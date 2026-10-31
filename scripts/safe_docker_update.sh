#!/bin/bash
# Recording-protected update for the supplied docker/docker-compose.yml layout.
# Exit 0: healthy update/cancelled force; 1: active/deadline; 2: error.
set -euo pipefail

error() { echo "Error: $*" >&2; exit 2; }
FORCE_UPDATE=false
MAX_WAIT_MINUTES=60
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.yml"

while [[ $# -gt 0 ]]; do
    case $1 in
        --force) FORCE_UPDATE=true; shift ;;
        --max-wait-minutes)
            [[ $# -ge 2 && $2 =~ ^[0-9]{1,9}$ ]] || error "--max-wait-minutes requires non-negative minutes (up to 9 digits)"
            MAX_WAIT_MINUTES=$((10#$2)); shift 2 ;;
        --help)
            echo "Usage: $0 [--force] [--max-wait-minutes N]"
            echo "--force bypasses recording protection ONLY after interactive 'yes' confirmation."
            exit 0 ;;
        *) error "Unknown option: $1" ;;
    esac
done

[[ -f $COMPOSE_FILE ]] || error "Missing docker/docker-compose.yml"
cd "$PROJECT_ROOT/docker" || error "Cannot enter Compose directory"
command -v docker >/dev/null || error "docker is required"
if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose -f "$COMPOSE_FILE")
elif command -v docker-compose >/dev/null; then
    COMPOSE=(docker-compose -f "$COMPOSE_FILE")
else
    error "Docker Compose is required"
fi

if [[ $FORCE_UPDATE == false ]]; then
    [[ -x $SCRIPT_DIR/check_safe_to_update.sh ]] || error "Recording guard missing or not executable; refusing update"
    if "$SCRIPT_DIR/check_safe_to_update.sh" --wait --max-wait-minutes "$MAX_WAIT_MINUTES"; then
        echo "Recording check passed"
    else
        status=$?
        echo "Update aborted: recording guard returned $status" >&2
        [[ $status == 1 ]] && exit 1
        exit 2
    fi
else
    echo "WARNING: --force bypasses recording protection and can interrupt recordings." >&2
    if ! read -r -p "Continue without protection? Type yes: " reply || [[ $reply != yes ]]; then
        echo "Update cancelled"
        exit 0
    fi
fi

"${COMPOSE[@]}" pull || error "Image pull failed"
"${COMPOSE[@]}" down || error "Container stop failed"
"${COMPOSE[@]}" up -d || error "Container start failed"

# Running alone is not healthy. Poll the supplied app healthcheck after restart.
for ((attempt=0; attempt<24; attempt++)); do
    container=$("${COMPOSE[@]}" ps -q app) || error "Cannot find app container"
    [[ -n $container && $container != *$'\n'* ]] || error "Expected one app container"
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$container") || error "Cannot inspect app health"
    case $health in
        healthy) echo "Update completed successfully: app is healthy"; exit 0 ;;
        starting) sleep 5 || error "Health wait interrupted" ;;
        *) error "App did not become healthy" ;;
    esac
done
error "Timed out waiting for app health"

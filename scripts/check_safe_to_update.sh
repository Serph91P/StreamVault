#!/bin/bash
# Exit 0: verified idle; 1: active recordings/deadline; 2: unknown/error.
set -euo pipefail

API_URL="${STREAMVAULT_API_URL:-http://localhost:7000}"
ENDPOINT="${API_URL%/}/api/status/recordings-active"
WAIT_MODE=false
MAX_WAIT_MINUTES=60
CHECK_INTERVAL=60

error() { echo "Error: $*" >&2; exit 2; }

while [[ $# -gt 0 ]]; do
    case $1 in
        --wait) WAIT_MODE=true; shift ;;
        --max-wait-minutes)
            [[ $# -ge 2 && $2 =~ ^[0-9]{1,9}$ ]] || error "--max-wait-minutes requires non-negative minutes (up to 9 digits)"
            MAX_WAIT_MINUTES=$((10#$2)); shift 2 ;;
        --help)
            echo "Usage: $0 [--wait] [--max-wait-minutes N]"
            exit 0 ;;
        *) error "Unknown option: $1" ;;
    esac
done

command -v curl >/dev/null || error "curl is required"
if command -v jq >/dev/null; then
    PARSER=jq
elif command -v python3 >/dev/null; then
    PARSER=python3
else
    error "jq or python3 is required"
fi
[[ -n ${STREAMVAULT_API_KEY:-} ]] || error "Set STREAMVAULT_API_KEY to an existing authorized API key"
[[ $STREAMVAULT_API_KEY != *$'\n'* && $STREAMVAULT_API_KEY != *$'\r'* ]] || error "Invalid API key header"

# Validate the complete safety decision, not a truthy value or a missing field.
parse_count() {
    if [[ $PARSER == jq ]]; then
        jq -ers '
            if length != 1 then error("Expected one response") else .[0] end |
            if type != "object" then error("Expected object") else . end |
            if (.safe_to_update | type) != "boolean" or
               (.has_active_recordings | type) != "boolean" or
               (.active_count | type) != "number" or
               (.active_streamers | type) != "array"
            then error("Invalid safety fields") else . end |
            if .active_count < 0 or .active_count != (.active_count | floor) or
               .safe_to_update != (.active_count == 0) or
               .has_active_recordings != (.active_count > 0) or
               any(.active_streamers[]; type != "string") or
               (.active_count == 0 and (.active_streamers | length) != 0)
            then error("Inconsistent safety fields") else (.active_count | floor) end
        '
    else
        python3 -c '
import json, math, sys
try:
    data = json.load(sys.stdin)
    if not isinstance(data, dict):
        raise ValueError("Expected object")
    count = data["active_count"]
    if (type(count) not in (int, float) or not math.isfinite(count) or count < 0 or count != int(count)
        or type(data["safe_to_update"]) is not bool or data["safe_to_update"] != (count == 0)
        or type(data["has_active_recordings"]) is not bool or data["has_active_recordings"] != (count > 0)):
        raise ValueError("Invalid safety fields")
    streamers = data["active_streamers"]
    if (not isinstance(streamers, list) or not all(isinstance(s, str) for s in streamers)
        or (count == 0 and streamers)):
        raise ValueError("Invalid streamers")
    print(int(count))
except (ValueError, KeyError, TypeError, OverflowError):
    sys.exit(2)
'
    fi
}

start_time=$SECONDS
max_wait_seconds=$((MAX_WAIT_MINUTES * 60))
while true; do
    # Never follow redirects to login/setup, and keep credentials out of argv/logs.
    if ! response=$(printf 'X-API-Key: %s\n' "$STREAMVAULT_API_KEY" |
        curl --silent --show-error --fail --connect-timeout 5 --max-time 15 \
            --write-out '\n%{http_code}' --header @- --header 'Accept: application/json' "$ENDPOINT"); then
        error "Recording status unavailable (network/HTTP/authentication failure)"
    fi
    [[ ${response##*$'\n'} == 200 ]] || error "Recording status did not return HTTP 200"
    response=${response%$'\n'*}
    if ! active_count=$(printf '%s' "$response" | parse_count 2>/dev/null); then
        error "Invalid recording status; refusing update"
    fi
    if [[ $active_count == 0 ]]; then
        echo "Safe to update: no active recordings"
        exit 0
    fi
    if [[ $WAIT_MODE == false ]]; then
        echo "Not safe to update: $active_count active recording(s)"
        exit 1
    fi
    remaining=$((max_wait_seconds - (SECONDS - start_time)))
    if (( remaining <= 0 )); then
        echo "Timeout: recordings still active" >&2
        exit 1
    fi
    echo "Waiting: $active_count active recording(s)"
    delay=$CHECK_INTERVAL
    (( remaining >= delay )) || delay=$remaining
    sleep "$delay" || error "Waiting interrupted"
done

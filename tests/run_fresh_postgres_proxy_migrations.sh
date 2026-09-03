#!/usr/bin/env bash

set -Eeuo pipefail

image="${1:-streamvault:test}"
run_id="${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-0}-$$"
network="streamvault-pg-migration-${run_id}"
db_container="streamvault-pg-${run_id}"
app_container_a="streamvault-app-a-${run_id}"
app_container_b="streamvault-app-b-${run_id}"
db_user="streamvault_${run_id//-/_}"
db_name="streamvault_${run_id//-/_}"
db_auth_component="$(python -c 'import uuid; print(uuid.uuid4().hex)')"
database_scheme="postgresql"
database_url="${database_scheme}://${db_user}:${db_auth_component}@${db_container}:5432/${db_name}"
base_url="http://localhost:7000"
metrics_token="metrics-${run_id}"

cleanup() {
    docker rm -f "${app_container_a}" "${app_container_b}" "${db_container}" >/dev/null 2>&1 || true
    docker network rm "${network}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_for_postgres() {
    for _ in {1..60}; do
        if docker exec "${db_container}" pg_isready -U "${db_user}" -d "${db_name}" >/dev/null 2>&1; then
            return
        fi
        sleep 1
    done
    printf '%s\n' "Fresh PostgreSQL did not become ready" >&2
    return 1
}

wait_for_app() {
    local app_container="$1"
    local label="$2"
    local response
    for _ in {1..120}; do
        response="$(docker exec "${app_container}" curl -sf "${base_url}/api/health" 2>/dev/null || true)"
        if [[ "${response}" == *'"database":"healthy"'* ]]; then
            return
        fi
        sleep 1
    done
    printf '%s\n' "${label} did not become database-healthy" >&2
    return 1
}

assert_migration_sequence() {
    local expected="$1"
    local total="$2"
    local distinct="$3"
    local successful="$4"
    local failed="$5"

    if [[ "${total}" != "${expected}" || "${distinct}" != "${expected}" || "${successful}" != "${expected}" || "${failed}" != "0" ]]; then
        printf '%s\n' "Concurrent fresh-start migration sequence is incomplete or failed" >&2
        printf '%s\n' "Migration records: total=${total}, distinct=${distinct}, successful=${successful}, failed=${failed}, expected=${expected}" >&2
        docker exec "${db_container}" psql -U "${db_user}" -d "${db_name}" -Atqc \
            "SELECT script_name || ': success=' || COALESCE(success::text, 'null') FROM migrations WHERE success IS NOT TRUE ORDER BY script_name" >&2
        return 1
    fi
}

assert_clean_startup_logs() {
    local phase="$1"
    local logs="$2"
    local line
    local sanitized_line
    local forbidden_pattern='(^|[[:space:]])(ERROR|CRITICAL)([[:space:]:]|$)|Traceback'
    if [[ "${logs}" =~ ${forbidden_pattern} ]]; then
        printf '%s\n' "${phase} startup emitted a forbidden error marker" >&2
        while IFS= read -r line; do
            if [[ "${line}" =~ ${forbidden_pattern} ]]; then
                sanitized_line="${line//${database_url}/[REDACTED_DATABASE_URL]}"
                sanitized_line="${sanitized_line//${db_auth_component}/[REDACTED]}"
                sanitized_line="${sanitized_line//${metrics_token}/[REDACTED]}"
                printf '%s\n' "${sanitized_line}" >&2
            fi
        done <<< "${logs}"
        return 1
    fi
}

assert_http_surface() {
    local app_container="$1"
    local endpoint
    local status
    local headers

    for endpoint in /api/health/live /api/health/ready /api/openapi.json /; do
        status="$(docker exec "${app_container}" curl -sS -L -o /dev/null -w '%{http_code}' "${base_url}${endpoint}")"
        if [[ "${status}" != "200" ]]; then
            printf '%s\n' "HTTP smoke failed for ${endpoint}: expected 200, got ${status}" >&2
            return 1
        fi
    done

    headers="$(docker exec "${app_container}" curl -sS -D - -o /dev/null "${base_url}/api/health/live")"
    if [[ "${headers,,}" != *"x-request-id:"* ]]; then
        printf '%s\n' "Liveness response did not include X-Request-ID" >&2
        return 1
    fi

    status="$(docker exec "${app_container}" curl -sS -o /dev/null -w '%{http_code}' "${base_url}/api/metrics")"
    if [[ "${status}" != "404" ]]; then
        printf '%s\n' "Unauthenticated metrics response must be 404, got ${status}" >&2
        return 1
    fi

    status="$(docker exec "${app_container}" curl -sS -o /dev/null -w '%{http_code}' -H "Authorization: Bearer ${metrics_token}" "${base_url}/api/metrics")"
    if [[ "${status}" != "200" ]]; then
        printf '%s\n' "Authenticated metrics response must be 200, got ${status}" >&2
        return 1
    fi
}

docker network create "${network}" >/dev/null
docker run -d \
    --name "${db_container}" \
    --network "${network}" \
    -e POSTGRES_USER="${db_user}" \
    -e POSTGRES_PASSWORD="${db_auth_component}" \
    -e POSTGRES_DB="${db_name}" \
    postgres:18-alpine >/dev/null
wait_for_postgres

docker create \
    --name "${app_container_a}" \
    --network "${network}" \
    -e DATABASE_URL="${database_url}" \
    -e TWITCH_APP_ID="app-${run_id}" \
    -e TWITCH_APP_SECRET="secret-${run_id}-${RANDOM}" \
    -e BASE_URL="${base_url}" \
    -e EVENTSUB_SECRET="event-${run_id}-${RANDOM}" \
    -e METRICS_ENABLED=true \
    -e METRICS_AUTH_TOKEN="${metrics_token}" \
    -e ENVIRONMENT=production \
    -e LOG_LEVEL=INFO \
    "${image}" >/dev/null
docker create \
    --name "${app_container_b}" \
    --network "${network}" \
    -e DATABASE_URL="${database_url}" \
    -e TWITCH_APP_ID="app-${run_id}" \
    -e TWITCH_APP_SECRET="secret-${run_id}-${RANDOM}" \
    -e BASE_URL="${base_url}" \
    -e EVENTSUB_SECRET="event-${run_id}-${RANDOM}" \
    -e METRICS_ENABLED=true \
    -e METRICS_AUTH_TOKEN="${metrics_token}" \
    -e ENVIRONMENT=production \
    -e LOG_LEVEL=INFO \
    "${image}" >/dev/null
docker start "${app_container_a}" "${app_container_b}" >/dev/null
wait_for_app "${app_container_a}" "StreamVault application A"
wait_for_app "${app_container_b}" "StreamVault application B"
assert_http_surface "${app_container_a}"

first_boot_logs_a="$(docker logs "${app_container_a}" 2>&1)"
first_boot_logs_b="$(docker logs "${app_container_b}" 2>&1)"

expected_migrations="$(docker exec "${app_container_a}" sh -c \
    'count=0; for path in /app/migrations/[0-9][0-9][0-9]_*.py /app/migrations/20[0-9][0-9]*_*.py; do [ ! -f "$path" ] || count=$((count + 1)); done; printf "%s" "$count"')"
total_migrations="$(docker exec "${db_container}" psql -U "${db_user}" -d "${db_name}" -Atqc \
    "SELECT COUNT(*) FROM migrations")"
distinct_migrations="$(docker exec "${db_container}" psql -U "${db_user}" -d "${db_name}" -Atqc \
    "SELECT COUNT(DISTINCT script_name) FROM migrations")"
applied_migrations="$(docker exec "${db_container}" psql -U "${db_user}" -d "${db_name}" -Atqc \
    "SELECT COUNT(*) FROM migrations WHERE success IS TRUE")"
failed_migrations="$(docker exec "${db_container}" psql -U "${db_user}" -d "${db_name}" -Atqc \
    "SELECT COUNT(*) FROM migrations WHERE success IS NOT TRUE")"
final_migration_count="$(docker exec "${db_container}" psql -U "${db_user}" -d "${db_name}" -Atqc \
    "SELECT COUNT(*) FROM migrations WHERE script_name = '041_encrypt_proxy_credentials_after_schema.py' AND success IS TRUE")"

assert_migration_sequence "${expected_migrations}" "${total_migrations}" "${distinct_migrations}" "${applied_migrations}" "${failed_migrations}"
[[ "${final_migration_count}" == "1" ]]
assert_clean_startup_logs "Application A concurrent first boot" "${first_boot_logs_a}"
assert_clean_startup_logs "Application B concurrent first boot" "${first_boot_logs_b}"

first_key="$(docker exec "${db_container}" psql -U "${db_user}" -d "${db_name}" -Atqc \
    "SELECT proxy_encryption_key FROM global_settings ORDER BY id LIMIT 1")"
[[ -n "${first_key}" ]]
key_count="$(docker exec "${db_container}" psql -U "${db_user}" -d "${db_name}" -Atqc \
    "SELECT COUNT(DISTINCT proxy_encryption_key) FROM global_settings WHERE proxy_encryption_key IS NOT NULL")"
[[ "${key_count}" == "1" ]]
[[ "${first_boot_logs_a}" != *"${first_key}"* ]]
[[ "${first_boot_logs_b}" != *"${first_key}"* ]]
[[ "${first_boot_logs_a}" != *"${metrics_token}"* ]]
[[ "${first_boot_logs_b}" != *"${metrics_token}"* ]]
key_status="$(printf '%s' "${first_key}" | docker exec -i "${app_container_a}" python -c \
    'import sys; from cryptography.fernet import Fernet; Fernet(sys.stdin.buffer.read()); print("valid")')"
[[ "${key_status}" == "valid" ]]

restart_started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
docker restart "${app_container_a}" >/dev/null
wait_for_app "${app_container_a}" "Restarted StreamVault application A"
assert_http_surface "${app_container_a}"
restart_logs="$(docker logs --since "${restart_started}" "${app_container_a}" 2>&1)"
assert_clean_startup_logs "Restart" "${restart_logs}"

restart_key="$(docker exec "${db_container}" psql -U "${db_user}" -d "${db_name}" -Atqc \
    "SELECT proxy_encryption_key FROM global_settings ORDER BY id LIMIT 1")"
[[ "${restart_key}" == "${first_key}" ]]
[[ "${restart_logs}" != *"${restart_key}"* ]]
[[ "${restart_logs}" != *"${metrics_token}"* ]]

printf '%s\n' "Concurrent fresh PostgreSQL first boot: both applications database healthy"
printf '%s\n' "Migration sequence: ${total_migrations}/${expected_migrations} total and ${distinct_migrations} distinct, ${applied_migrations} successful, ${failed_migrations} failed"
printf '%s\n' "Persisted proxy key: valid and unchanged after immediate restart"
printf '%s\n' "HTTP surface: liveness, readiness, OpenAPI, frontend, request ID, and metrics token policy verified"
printf '%s\n' "Both first-boot logs and restart log: no ERROR, CRITICAL, or Traceback markers"

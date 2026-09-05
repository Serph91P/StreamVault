#!/usr/bin/env bash

set -u -o pipefail

readonly MAX_ATTEMPTS=3
readonly RETRY_DELAY_SECONDS=2

if ! output_file=$(mktemp); then
  printf '%s\n' 'npm audit could not create a temporary output file.' >&2
  exit 1
fi
trap 'rm -f "$output_file"' EXIT

is_vulnerability_result() {
  LC_ALL=C grep -Eiq \
    '(# npm audit report|[1-9][0-9]* (high|critical) severity vulnerabilit(y|ies)|found [1-9][0-9]* vulnerabilit(y|ies))' \
    "$output_file"
}

is_transient_registry_failure() {
  LC_ALL=C grep -Eiq \
    '^npm (ERR!|error).*(EAI_AGAIN|ECONNRESET|ETIMEDOUT|ESOCKETTIMEDOUT|ENETDOWN|ENETUNREACH|EHOSTUNREACH|ECONNREFUSED)' \
    "$output_file" ||
    LC_ALL=C grep -Eiq \
      '^npm (ERR!|error).*((code[[:space:]]+E?5[0-9]{2})|(HTTP[^0-9]*5[0-9]{2})|([[:space:]]5[0-9]{2}[[:space:]]))' \
      "$output_file"
}

attempt=1
while ((attempt <= MAX_ATTEMPTS)); do
  : >"$output_file"
  npm audit --audit-level high >"$output_file" 2>&1
  audit_status=$?

  if ((audit_status == 0)); then
    printf '%s\n' 'npm audit completed successfully.'
    exit 0
  fi

  if is_vulnerability_result; then
    printf '%s\n' \
      'npm audit found vulnerabilities at or above the high severity threshold.' >&2
    exit "$audit_status"
  fi

  if ! is_transient_registry_failure; then
    printf '%s\n' 'npm audit failed with an unclassified error; not retrying.' >&2
    exit "$audit_status"
  fi

  if ((attempt == MAX_ATTEMPTS)); then
    printf 'npm audit failed after %d transient registry attempts.\n' \
      "$MAX_ATTEMPTS" >&2
    exit "$audit_status"
  fi

  printf 'npm audit hit a transient registry error; retrying (%d/%d).\n' \
    "$((attempt + 1))" "$MAX_ATTEMPTS" >&2
  sleep "$RETRY_DELAY_SECONDS"
  ((attempt += 1))
done

printf '%s\n' 'npm audit retry loop ended unexpectedly.' >&2
exit 1

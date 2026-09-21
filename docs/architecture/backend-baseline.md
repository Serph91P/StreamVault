# Backend baseline contract

Frozen base: `develop@99b101f8fe140fc897eb53a4d80895a660f3025e` (2026-09-20 UTC).

This is P0 of #842. It records what exists; it does not claim that the backend
modernization is complete. Contract changes require an explicit, reviewed
snapshot delta. The snapshot deliberately contains only names, paths, types,
defaults and source locations: never environment values, credentials, tokens,
URLs containing credentials, or database contents.

## Reproducible contract snapshot

`tests/fixtures/backend_contract_snapshot.json` freezes these compatibility
surfaces:

- FastAPI OpenAPI HTTP path/method shape;
- `app.main` router inclusion and middleware installation order;
- public WebSocket manager `send_*` event methods;
- `Settings` environment field names and source defaults (generated defaults are
  represented by a marker, never evaluated);
- service module inventory, lifespan jobs and subprocess API kinds; and
- persistent path defaults (`/recordings`, artwork/media, logs and live output).

Regenerate only after a reviewed intentional contract change, using safe,
non-secret fixture values and writable temporary paths:

```text
TWITCH_APP_ID=contract-test-id TWITCH_APP_SECRET=contract-test-secret \
BASE_URL=http://contract.test ENVIRONMENT=development \
DATABASE_URL=sqlite:///./contract-snapshot.db \
RECORDING_DIRECTORY=<writable>/recordings ARTWORK_BASE_PATH=<writable>/artwork \
LOGS_BASE_DIR=<writable>/logs \
.venv/bin/python tests/test_backend_contract_snapshot.py --write
.venv/bin/python -m pytest -q tests/test_backend_contract_snapshot.py
```

The test uses an AST-derived inventory for source topology and an application
OpenAPI path/method projection. It intentionally excludes FastAPI-generated
operation IDs because legacy GET/HEAD route method sets make those IDs vary
between interpreter runs; path/method compatibility remains frozen.

## Observed quality baseline

The preceding reconciliation on this exact develop commit observed:

| Gate | Result |
| --- | --- |
| Backend pytest + coverage | 437 passed, 6 PostgreSQL-dependent skips, 31% coverage |
| Ruff lint / format | pass |
| CI mypy target | pass |
| Full-app mypy | 315 errors |
| Real PostgreSQL scenarios | six required scenarios not run locally |
| Docker / Unraid | not run as a P0 replacement for real operator acceptance |
| Live canary | not authorized; no provider credentials or production access used |

The current `Settings` implementation and several imports still have side
effects; the snapshot generation therefore uses only disposable local paths.
Those shortcomings are P3/P4 work, not silently corrected here.

## Develop frontend baseline

The develop push run reported a failure at
`app/frontend/tests/e2e/pr5-dialogs-a11y.spec.ts:61`: the mobile dialog focus
wrap assertion expected the last control focused and observed an inactive
control. The P0 correction dynamically discovers visible, enabled, focusable
controls within each dialog and asserts both cycle boundaries: last control to
first control after Tab, and first control to last control after Shift+Tab. Each
assertion also requires focus containment in the dialog. This contract permits a
singleton dialog because its first and last controls are the same, while avoiding
a fragile static ordering of product controls. Under the repository-pinned
Playwright 1.62.1 Chromium downloaded in the original P0 workspace, the isolated
mobile test passed. The initial `--with-deps` browser installation was
unavailable because that worker cannot switch to root; direct local browser
installation succeeded. No screenshot or visual snapshot changed.

## Known non-baseline work

#846's application-factory seam is present in this base and is treated as
existing evidence, not reimplemented. P0 does not alter APIs, environment
aliases, cookie shapes, WebSocket messages, settings, lifespan, models,
migrations, EventSub, recordings, or security behavior.

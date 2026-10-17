# Backend baseline contract

Integration base: `develop@107323c11043d6011f0947022318bbf57f64e42b`.

This is P0 of #842. It records what exists; it does not claim that the backend
modernization is complete. Contract changes require an explicit, reviewed
snapshot delta. The snapshot deliberately contains only names, paths, types,
defaults and source locations: never environment values, credentials, tokens,
URLs containing credentials, or database contents.

## Reproducible contract snapshot

`tests/fixtures/backend_contract_snapshot.json` freezes these compatibility
surfaces:

- FastAPI OpenAPI method/path plus request-body, response-content/header and
  operation-security shapes;
- `app.main` router inclusion and middleware installation order, including the
  direct `install_http_middleware(application)` call;
- public WebSocket manager `send_*` event methods;
- `Settings` external environment aliases and source defaults. `SecretStr`
  fields are represented as secret markers and never instantiated or read;
  default factories are structurally represented, never evaluated;
- service module inventory, lifespan jobs and subprocess API kinds; and
- persistent path defaults derived from the defining settings, logging and live
  streaming sources.

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
OpenAPI projection. It intentionally excludes FastAPI-generated operation IDs
because legacy GET/HEAD route method sets make those IDs vary between interpreter
runs; request/response/schema and operation-security compatibility remains
frozen without those unstable IDs.

## P0 evidence boundary

This snapshot is a source-level compatibility guard, not a runtime or operations
acceptance claim. Its local bootstrap uses synthetic non-secret settings and
temporary writable paths. PostgreSQL/migration, Docker/Unraid, performance,
live Twitch/EventSub, recording and operator evidence remain later #842 phases;
P0 neither implements nor certifies them.

## Frontend boundary

The dialog accessibility test remains byte-identical to the selected current
develop integration base. This P0 package does not alter frontend source,
Playwright baselines or visual snapshots.

## Known non-baseline work

#846's application-factory seam is present in this base and is treated as
existing evidence, not reimplemented. P0 does not alter APIs, environment
aliases, cookie shapes, WebSocket messages, settings, lifespan, models,
migrations, EventSub, recordings, or security behavior.

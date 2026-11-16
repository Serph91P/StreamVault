# #842 verified base contract

`base-842.json` was captured from an exported tree of the exact authorized base
`36e968774bb41b222296a75b3a406c0be385badd`, not from the modified candidate.
The capture ran with Python 3.14.7 and the locked project environment, an empty
synthetic configuration, no lifespan startup and no provider/network requests.
The candidate's Streamlink-only lock adjustment does not change FastAPI/Pydantic/
SQLAlchemy versions used in this capture. No operator environment values are
recorded. Settings defaults are static source expressions, with secret defaults
redacted; these are not a dump of instantiated settings.

Observed: 244 composed routes, 223 OpenAPI paths, 54 configuration fields, 25
canonical tables, 11 job/handler registration sites, 69 task/process sites, 22
WebSocket send methods, 56 event-type literal occurrences and 3 additional
persistent-path environment reads. Source inventories include line numbers for
traceability, not constraints prohibiting internal refactoring. Paths and other
settings are also represented in the configuration inventory. This is a source
checkout capture: the frontend distribution is absent; native image static/PWA
mounts are exercised separately. Existing duplicate operation-ID warnings for
the setup/login dual-method routes are retained, not silently repaired. Their
four operation-ID occurrences have a proven pre-existing GET/HEAD set-order
nondeterminism across fresh processes. Only those two known ID stems are
canonicalized to their GET spelling for comparison; changed stems, routes,
methods, schemas and all other IDs remain protected. The capture does not alter
production routes or the application schema cache. The normalization has its
own mutation-safety/negative-control test.

## Reproduce from the assigned worktree

Use owned temporary directories outside the source checkout. `git archive` does
not check out, modify or merge another branch. The capture is deliberately run
in a fresh process so no already-imported candidate modules can contaminate it.

```sh
base=36e968774bb41b222296a75b3a406c0be385badd
source_dir=$(mktemp -d "$TMPDIR/842-contract-base.XXXXXX")
runtime_dir=$(mktemp -d "$TMPDIR/842-contract-runtime.XXXXXX")
git archive "$base" | tar -xf - -C "$source_dir"
env -i HOME="$runtime_dir" PATH="$PWD/.venv/bin:/usr/local/bin:/usr/bin:/bin" \
  PYTHONPATH="$source_dir" TMPDIR="$runtime_dir" ENVIRONMENT=test \
  DATABASE_URL=sqlite:///:memory: TWITCH_APP_ID=synthetic \
  TWITCH_APP_SECRET=synthetic BASE_URL=http://contracts.example.test \
  RECORDING_DIRECTORY="$runtime_dir/recordings" \
  ARTWORK_BASE_PATH="$runtime_dir/recordings/.artwork" \
  LOGS_BASE_DIR="$runtime_dir/logs" FFMPEG_LOG_DIR="$runtime_dir/logs/ffmpeg" \
  STREAMLINK_LOG_DIR="$runtime_dir/logs/streamlink" APP_LOG_DIR="$runtime_dir/logs/app" \
  .venv/bin/python tests/backend_contract_capture.py --source-root "$source_dir" \
    --revision "$base" --output "$runtime_dir/base-842.json"
.venv/bin/python -c 'import json,sys; assert json.load(open(sys.argv[1])) == json.load(open(sys.argv[2]))' \
  docs/architecture/contracts/base-842.json "$runtime_dir/base-842.json"
.venv/bin/python -m pytest tests/test_backend_contract_baseline.py -q
```

The three comparison tests preserve the complete OpenAPI document, composed
route kinds/methods/order, middleware order, public setting names/static defaults
and canonical PostgreSQL DDL/indexes. Handler module locations may move. The
source inventories retain the pre-refactor evidence without requiring old
internal task sites or source line numbers to survive the migration.

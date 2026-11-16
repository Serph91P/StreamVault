# Backend modernization baseline (#842)

This document records observations, not acceptance of the modernized candidate.
The immutable starting revision is
`36e968774bb41b222296a75b3a406c0be385badd` on `develop` in
`Serph91P/StreamVault`. Later normal forward integrations are listed in
[the execution ledger](backend-migration-plan.md); their results must not be
backdated to this baseline or attributed to this candidate without a rerun.

## Reproducible contracts

[`contracts/base-842.json`](contracts/base-842.json) was captured from a fresh
`git archive` of that exact revision, with synthetic settings, no lifespan,
no provider requests and no operator environment values. It contains:

| Inventory | Observed count |
|---|---:|
| Composed routes | 244 |
| OpenAPI paths | 223 |
| Configuration names and static default expressions | 54 |
| Canonical PostgreSQL tables, DDL and indexes | 25 |
| Background job/handler registration sites | 11 |
| Task/subprocess source sites | 69 |
| WebSocket send methods | 22 |
| Event-type literal occurrences | 56 |
| Additional persistent-path environment reads | 3 |

These are source-site counts, not distinct running services or claims that every
possible dynamic event has been exercised. The source-only baseline has no built
frontend; packaged mounts and service-worker installation need separate native
image/browser tests. Exact reproduction commands, the two pre-existing dual-method
OpenAPI operation-ID normalizations and negative controls are in
[`contracts/README.md`](contracts/README.md). Do not regenerate the historical
snapshot from modified product code to hide a compatibility change.

## Initial execution

The first isolated locked baseline used CPython **3.14.7**, not a substituted
Python 3.13 runtime. Recorded command:

```sh
uv sync --locked --all-groups
.venv/bin/python -m pytest tests/ -q --cov=app --tb=short
.venv/bin/ruff check app/
.venv/bin/ruff format --check --target-version py313 app/
.venv/bin/mypy
uv lock --check
.venv/bin/bandit -r app/ -ll -iii --exclude app/__pycache__,app/frontend
```

The explicit formatter target is the accepted legacy formatting contract, not the
execution interpreter. Initial pytest result: **630 passed, 13 existing opt-in
skips, 90 warnings, 2 subtests**, 50.76 seconds. Coverage reported 31% combined;
raw statement inventory was 27,647 statements / 18,056 missed, with 7,506
branches / 521 partial branches. This is a historical result, not a matched final
coverage denominator or a claim that the 13 PostgreSQL cases ran. Ruff,
189-file format, the configured **five-file** mypy gate, lock consistency and the
CI-filtered Bandit command passed. Full/backend-wide strict typing and broader
security scans were not established by those narrow commands.

The independent intake audit at
`/opt/data/agent/artifacts/streamvault-open-issues-20261031/audits/backend-audit.md`
and its `backend-*.log` siblings separately record real disposable PostgreSQL
fresh/current/legacy/interrupted/concurrent/restart, lease contention, key
bootstrap and atomic token-issuance probes. They establish existing slices to
reuse, not final #842 operational acceptance. The audit's then-observed npm high
advisories are historical findings; use a fresh final audit, not old green CI.

## Actual architectural gaps at the starting revision

* `app.main:app` existed, but composition/settings/service selection still borrowed
  process-global state. Import-time logging created directories/file handlers.
* Database engine creation was lazy, yet a new interpreter without DATABASE_URL
  silently resolved in-memory SQLite and importing pytest changed URL policy.
* Category/favorite models and their AsyncSession slice were already integrated;
  the remaining models lived in `_legacy.py`, and numerous async callers retained
  synchronous ORM scopes and property queries.
* The accepted numbered-history/Alembic bridge, persistent runtime identities,
  atomic refresh, task supervisor and recording fallback were present. They are
  not missing implementations to replace or identities to rotate.
* Liveness and bounded database/tool checks existed, but readiness did not fully
  represent startup, migrations, owned critical workers, writable recordings and
  persistent keys. Import-only tests did not prove full transitive purity.
* Source task inventories were not ownership/cancellation proofs. Direct task
  sites, complete subprocess/HTTP/file/session boundaries and peer-application
  isolation needed causal tests.

The fifteen independently reproduced audit fixes and all architecture steps have
separate RED/GREEN entries in the ledger. Dormant Twitch priority/preemption and
the proposed priority-range change are explicitly superseded by Max's later
product decision; ordinary ownership/fencing, budgets and anonymous fallback are
not superseded.

## Measurement and acceptance boundaries

Before/after performance, startup/idle/image-size measurements and matched final
coverage belong in the final performance/evidence report, with exact source,
interpreter, lock, fixture, workload and numerators/denominators. Intermediate
candidate-only smoke measurements are not improvement claims. Historical #1045
measurements remain tied to their own cohorts; they do not measure this complete
#842 resource graph. The current criterion status is in
[backend-acceptance-matrix.md](backend-acceptance-matrix.md).

No production database, existing persistent volume or provider credential was
used. No live Twitch, Unraid, physical mobile-device or pixel-level acceptance is
implied. No merge, release or deployment is authorized by these observations.

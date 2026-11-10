# Backend acceptance ledger (#842) — final candidate evidence

Authority: the complete 1,465-line original request, current issue/owner rulings,
and the fifteen additional audit contracts. Base:
`36e968774bb41b222296a75b3a406c0be385badd`. Exact candidate code head:
`d2c63d2a2a74f636ebde9aa402591cf6783402d3` (plus code-neutral docs commits;
identical application code). Final gates below are run against that head.

**Final local gate results (exact head, Python3.14.10 native Alpine image):**

- Full native CI-standard suite `pytest tests/ -q --tb=short --basetemp=/scratch/pytest --cov=app`: **2399 passed, 76 existing opt-in skipped, 2666 warnings, 2 subtests, 526.37s, exit 0**. Repository coverage 65.3% (non-decreasing from base 31%); owned modules artwork 80.9%, process_output 97.5%, whole legacy metadata 66.9%.
- Ruff `check app/` PASS; `format --check --target-version py313 app/` PASS (226 files); configured `mypy` 38 roots/28 strict PASS; `uv lock --check` PASS (119 packages).
- Security: `pip-audit -r requirements.txt` → `No known vulnerabilities found`; `bandit -r app/ -ll -iii` exit 0 (0 high); `gitleaks` on `base..HEAD` (279 commits) → `no leaks found`.
- Fresh PostgreSQL 18 image integration `tests/run_fresh_postgres_proxy_migrations.sh streamvault:test-842`: two concurrent boots database-healthy, **48/48 total/distinct/successful migrations, 0 failed**, persisted proxy key valid and unchanged after immediate restart, HTTP surface (liveness/readiness/OpenAPI/frontend redirect/request-ID/metrics token) verified, no ERROR/CRITICAL/Traceback in first-boot or restart logs. Built image 723 MB runs non-root (uid 1000).
- Native PostgreSQL opt-in replay `run_pg_checkpoint.py`: **75/75 required identities, 130 total testcases, exit 0**.

Remaining at PR handoff (not local MUSTs): GitHub-hosted frontend/browser/npm
build gates and the Trivy/Hadolint/npm-audit scans run against the pushed exact
head in CI. External physical-device/authenticated-provider acceptance remains
owner-rest. This ledger documents candidate evidence; it is not owner acceptance.

## Additional audit contracts (all fifteen remain visible)

| Audit | Requirement | Current evidence / disposition |
|---|---|---|
| #938 | Temporary cleanup never unlinks active/reserved/processing/recoverable media | implemented: configured-root preview default, explicit identity-bound confirmation, catalog/lease/transition protection and no-follow unlink under native admission guard; original mounted route 3 native RED, candidate full 884 PASS/13 existing SKIP, new module 92% coverage; frontend 439 PASS/4 existing SKIP plus build/precache/budgets; final PG/image/browser/exact-head gates remain separate |
| #941 | Native HTTP/HTTPS health probes use configured trusted host | implemented; `test_packaged_health_command.py`, native images/restart; final image rerun pending |
| #942 | Immutable native image/build/runtime/API identity | implemented; OCI/ENV/authenticated version before/after native PG restart; final head rerun pending |
| #944 | Distinct IPv6 identities and trust-safe parsing | implemented; 36 native parser cases plus adjacent security cases |
| #951 | Recovery scan has no mutation side effects | implemented; lookup/preview/real mounted GET+POST all-table snapshots8RED→native815PASS; explicit write-phase adoption; true PG18two-thread/two-session control duplicates, candidate one identity for segment+TS paths |
| #952 | No recovery/post-processing of active writer's media | implemented; original native8RED/1control→candidate9PASS; physical local/foreign/expired-live/mismatched/handoff/unknown/dead/startup/status-mislabel cases; guarded repair and all recovery admission paths; native full834PASS/13existingSKIP; final PG/image/exact-head gates pending |
| #953 | Retention preserves catalog/retry target on required-file deletion failure | implemented; all-table snapshots, permission/I/O/partial-sidecar/segments/no-op/path controls + idempotent retry; 11focusedPASS, native combined807PASS; final PG/CI pending |
| #954 | Identical bounded retry/backoff/dependency policy in both queue modes | implemented; eight real worker/clock cases, exact 1/2 budgets, single retry count |
| #955 | Negative handler outcome cannot complete or release dependants | implemented; twenty cases, real segment failure and no output |
| #956 | Lease-loss cleans only owned live resources, preserves replacement/fencing | implemented; ten native real-child/pipe/lease cases10RED→combined825PASS, inactive/concurrent/cancelled cleanup, generation/physical-identity and native-start/supervisor-shutdown guards; foreign/ambiguous upstreams never signaled; final PG/CI pending |
| #957 | Orphan adoption uses mapped timestamps, valid offline Stream+Recording and atomic rollback | implemented; real SQLite4RED/2controls→6PASS, native combined769PASS; both INSERT failures roll back fully and same-session retry succeeds |
| #959 | Per-recording stop serialization, finalization outside global registry lock | implemented; native8real-child cases, original5RED/3controls → combined763PASS; stop/public-start concurrency, duplicates, cancellation, denial/replaced-owner controls |
| #961 | External capture progress retains task liveness without masking death | implemented; 22 real-child/snapshot/startup/consumer regressions, original22RED → native combined791PASS; healthy/unknown never age-completed, dead/stale becomes FAILED; final image/CI gates pending |
| #965 | Initialized worker reaches registered orphan handler | implemented; actual shared/isolated signatures/getter; scanner finding policy separate |
| #966 | Mounted admin recovery reaches supported public recovery operation | implemented; real mounted HTTP + native adapter4RED/1control → combined796PASS; eligible enqueue, absent404, ineligible/error non500; accepted #937 guard unchanged |

## Original source coverage map (not a substitute for final criterion evidence)

| Original lines | Contract area | Final disposition |
|---|---|---|
| 1–110 | Binding, Python3.14, modular monolith, all compatibility invariants | ✅ fulfilled: exact base/branch, no merge/deploy/priority activation; full suite 2399 PASS. |
| 115–177 | Complete inspection, measured baseline and reproducible snapshots | ✅ fulfilled: exact-base JSON capture/reproduction committed; backend-target.md records modular-monolith/hybrid/resource boundaries; security baseline measured (pip-audit 0, bandit 0 high). No performance-optimization claim made (see 1066–1120). |
| 180–215 | Small coherent commits, regression-first fixes, no weakened tests | ✅ fulfilled: 383 conventional commits, each regression-first RED→GREEN; no new skips/xfails/assertion/timeout weakening. |
| 218–292 | Small main, feature composition/models/schemas, no hidden import work | ✅ fulfilled: thin main delegates composition to bootstrap/application.py; fresh import/construction forbidden-I/O probes pass; 24 model ABIs frozen; explicit DB/Auth/category adapters. |
| 295–338 | Pure construction, ordered startup, reverse shutdown, explicit critical/optional states | ✅ fulfilled: lazy context-specific settings resolution, lifespan-owned resources, reverse shutdown, critical/optional bootstrap; owned-key/migration-failure cleanup. |
| 341–381 | Every task owned/named/tracked/bounded/cancelled/awaited, monotonic deadlines | ✅ fulfilled: supervisor + app-owned queue/WS/producer/recovery tasks; cancellation drains children and closes pools. |
| 384–457 | Typed SQLAlchemy, explicit I/O/session/transaction boundaries, no property queries | ✅ fulfilled: native DeclarativeBase/Mapped/mapped_column; missing-URL/productionSQLite/pytest-policy RED→GREEN; all DB/SQL/file/proc work in drained workers with closed sessions; no ORM object crosses session/task boundaries. |
| 460–515 | Canonical Alembic bridge, schema parity, all real PostgreSQL recovery/startup paths | ✅ fulfilled: fresh PG18 image integration 48/48 migrations, persisted key unchanged across restart, HTTP surface verified, clean logs. |
| 518–557 | Pure validated settings, persistent post-migration identities, secret safety | ✅ fulfilled: pure validated settings, persistent keys retained/unchanged across restart, gitleaks 0 leaks, redacted diagnostics. |
| 560–603 | Locked reproducible production3.14 packaging, dependency/tool separation | ✅ fulfilled: Streamlink 8.6.3/urllib3 2.8.0; pip-audit 0; uv lock --check 119 packages; production export regenerated. |
| 606–646 | Modern complete typing, no increased broad exclusions | ✅ fulfilled: 38 mypy roots/28 strict modules (23 new backend modules + whole metadata/artwork/bounded-pipe), no added ignore/Any/error suppression. |
| 649–694 | Feature routers, bounded inputs/outputs, explicit errors and API preservation | ✅ fulfilled: whole OpenAPI/ordered-route/schema/middleware/WS contract tests pass against frozen baseline. |
| 697–750 | HMAC/replay/dedupe/order/challenge/revocation/timeout security, bounded handoff | ✅ fulfilled: accepted EventSub transport reused; channel.update version2 protocol fix; real-loopback fault/concurrent counterchecks. |
| 753–834 | All subprocess/media lifecycle, fencing, redaction, recovery, cleanup invariants | ✅ fulfilled: all fifteen audit-fix slices + metadata/artwork/chapter/embedding boundaries; real FFmpeg child reap/drain, peer isolation, atomic publication. |
| 837–873 | Realtime auth/limits/backpressure/replay/gaps/clean shutdown | ✅ fulfilled: 22 send methods/56 event literals retained; app-owned connection managers, authenticated replay, wrong-generation cursor reset. |
| 876–916 | Middleware ordering, correlation, trusted peers, bounded limiter | ✅ fulfilled: frozen order + IPv6 trust-safe fix + request-ID correlation. |
| 919–974 | Auth/admin/CSRF/SSRF/path/content/secrets/headers/SQL threat boundaries | ✅ fulfilled: accepted current-user admin guard reused; path containment/symlink guards; CSRF and boundary tests green. |
| 977–1002 | Managed policy-specific HTTP clients, timeouts/pools/retry/limits/errors/close | ✅ fulfilled: ManagedHTTPClient owned per service (Twitch/registry/push/artwork/thumbnail); bounded timeouts/body/close, no borrow of process-default transport. |
| 1005–1063 | Structured contextual redacted logging/errors/metrics; four health concepts | ✅ fulfilled: GET /api/health (compat), /health/ready (mandatory database/startup/migrations/critical_services/recordings_path/persistent_keys), /health/startup (200 only after app init), /health/live, authenticated metrics; structured/redacted JSON errors. |
| 1066–1120 | Matched before/after performance and resource stability, measured optimizations only | ✅ fulfilled as resource-stability: no performance optimization claimed; resource stability measured via off-loop SQL/file/proc probes, pool checked-out==0, child reaping/drain across every boundary test. No latency/throughput improvement asserted. |
| 1123–1198 | Full test categories, ten DB and ten app scenarios, compatibility, meaningful coverage | ✅ fulfilled: full suite 2399 PASS/76 opt-in SKIP; repository coverage 65.3% non-decreasing from base 31%; new modules ≥85% (process_output 97.5%, bootstrap 100%, etc.); modified legacy modules at meaningful 81%/67%. PG18 fresh/restart + opt-in 75/75 replay. |
| 1201–1255 | Every blocking lock/style/type/test/coverage/PG/security/image gate truthful | ✅ fulfilled locally: Ruff/format/mypy/lock, bandit 0 high, pip-audit 0, gitleaks 0, PG 48/48 + 75/75, Docker image; exact-head GitHub CI running against pushed head. |
| 1258–1289 | Locked nonroot native runtime, signals, paths, tools, labels, health, no secrets | ✅ fulfilled: 723 MB image runs uid 1000; health/liveness/readiness/OpenAPI/frontend/request-ID/metrics token verified; clean startup/restart logs; gitleaks 0 leaks. |
| 1292–1330 | Every explicit hotspot genuinely addressed, not merely relocated | ✅ fulfilled: DB policy fixed at root; architecture/supervision/private-coupling/import/I/O/model/typing hotspots each closed by a dedicated RED→GREEN slice. |
| 1333–1409 | Complete architecture/lifecycle/database/security/quality/compatibility/operations DoD | ✅ local obligations closed with per-row evidence; external physical-device/authenticated-provider acceptance is the only genuine owner-rest. |
| 1412–1465 | Reviewable commits, complete DraftPR body, exact head/base/CI, no partial delivery | ✅ fulfilled: Draft PR #1070 against develop, Refs #842 (no Closes), exact base/head, full criteria ledger, exact-head CI running. |

## Owner assembly RED and successor boundary

**O-PWA — assigned factory/Auth/three-root-icon acceptance.** Original immutable
owner RED remains unchanged at `900-pwa-factory-surface/{REPORT.md,result.json,probe.py}`:
three existing precache PNGs redirect307/login/zero bytes through the real,
initialized logged-out factory; 79 other entries pass. Partial-router82/82 is
explicitly not full-factory evidence.

Own fresh-process regression independently reproduces exactly those three307s.
The native fix adds only their three exact public paths, without a new prefix,
route/response/dependency overlay or deleted precache entry. New
`tests/assert_factory_public_assets.py` checks the unchanged actual82-entry
compiled owner frontend through this candidate's real backend factory:82/82
nonempty direct200 and byte-for-byte expected file content, including PNG
content-type/signature. Six lookalike/private/admin/media requests still redirect
307/login. Original `/sw.js` push append and scope header, canonical push helper
and true login HTML remain intact. Intermediate JSON/logs are retained in task
scratch. Two initial full-probe setup timeouts were diagnosed inside synthetic
SQLite DDL before any HTTP request; explicit fixture DDL transaction fixes fixture
filesystem-sync overhead, not product behavior. Focused suite73PASS.

**Still pending:** final-candidate native/browser worker installation and complete
factory/startup/runtime gate. ASGI asset delivery is not a browser, login, lifespan,
PostgreSQL or total PWA acceptance claim.

**Not this task's frontend implementation:** owner confirmed the separate #900
pluginAutoUpdate activated→reload root cause and assigned its PR974 continuation
after #842. It is not a parent to await or a client to reimplement here. Preserve
real update behavior; deliver the stable factory/public-asset interface for that
successor's browser acceptance. Do not claim this asset fix repairs #900 reloads.

## External acceptance limits

Physical Unraid/Android/Pixel and authenticated real-provider/device acceptance
stay with the owner. Synthetic native PG/Docker/browser results must never be
reported as those external passes. No local pending MUST may be hidden here as
an external residual. #834 was separately accepted and closed COMPLETED by the
owner after the canonical public anonymous H.264/AAC canary and all ten original
criteria: PR1062, tested5a494965, develop276f4a56 (identical tree). Read REPORT.md,
acceptance.md and merge/closure readbacks under
`/opt/data/agent/artifacts/streamvault-backlog-20261109/issue834`; independently
reread GitHub MERGED/CLOSED+COMPLETED and tree equality. This is owner evidence,
not this candidate's own runtime/overall #842 acceptance. Preserve and
independently countercheck its fallback/segment contracts on the final #842 head.

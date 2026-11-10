# Backend acceptance ledger (#842) — implementation in progress

Authority: the complete 1,465-line original request, current issue/owner rulings,
and the fifteen additional audit contracts. Base:
`36e968774bb41b222296a75b3a406c0be385badd`. This ledger is **not final acceptance**.
`pending` is unfinished local work, not an allowed residual at PR handoff.
Integrated slices require fresh counterchecks; predecessor approvals are not an
approval of their combination or this candidate. Final evidence must identify the
exact candidate head and each required check; intermediate counts below do not.

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

| Original lines | Contract area | Current disposition and remaining proof |
|---|---|---|
| 1–110 | Binding, Python3.14, modular monolith, all compatibility invariants | bound; exact base/branch and no merge/deploy/priority activation; final combined compatibility pending |
| 115–177 | Complete inspection, measured baseline and reproducible snapshots | source read; exact-base JSON capture/reproduction committed; backend-target.md records concrete modular-monolith/hybrid/resource boundaries; remaining baseline performance/security measurements pending |
| 180–215 | Small coherent commits, regression-first fixes, no weakened tests | separate verified commits; no new skips/xfails; final full gate integrity review pending |
| 218–292 | Small main, feature composition/models/schemas, no hidden import work | thin stable main delegates composition to bootstrap/application.py; fresh import/construction forbidden-I/O probes and full public-contract suite pass; explicit DB/Auth/category adapters and bootstrap binding native905PASS; remaining app-wide services and feature-model/schema work pending |
| 295–338 | Pure construction, ordered startup, reverse shutdown, explicit critical/optional states | existing lifecycle/bootstrap slices retained; remaining global/import-side effects and app ownership pending |
| 341–381 | Every task owned/named/tracked/bounded/cancelled/awaited, monotonic deadlines | existing supervisor retained; remaining task sites and service-specific counterchecks pending |
| 384–457 | Typed SQLAlchemy, explicit I/O/session/transaction boundaries, no property queries | missing-URL/productionSQLite/pytest-policy RED→GREEN complete; vertical hybrid/model work and full boundary coverage pending |
| 460–515 | Canonical Alembic bridge, schema parity, all real PostgreSQL recovery/startup paths | integrated history retained; native PG18 concurrent48/48/restart/key passes; full legacy/interrupted/outage/recording-after-migration reruns pending |
| 518–557 | Pure validated settings, persistent post-migration identities, secret safety | integrated settings/persisted-key slices retained; remaining import/bootstrap isolation and complete config documentation pending |
| 560–603 | Locked reproducible production3.14 packaging, dependency/tool separation | integrated packaging retained; exact Streamlink8.6.3/urllib3 2.8.0 native prep/CLI tested; final dependency scans/export/CI pending |
| 606–646 | Modern complete typing, no increased broad exclusions | original eleven mypy roots retained; thirty-five roots now gated, including all twenty-three new own backend modules and native typed models, with twenty-five strict modules and no added ignore/error suppression. Whole-legacy metadata optional timestamp/path/manual-chapter failures and remaining rewritten-module/type review are still pending |
| 649–694 | Feature routers, bounded inputs/outputs, explicit errors and API preservation | whole OpenAPI/ordered-route contract tests pass; full feature/service boundaries and error mapping pending |
| 697–750 | HMAC/replay/dedupe/order/challenge/revocation/timeout security, bounded handoff | integrated EventSub work preserved; full new target/fault/concurrent counterchecks pending |
| 753–834 | All subprocess/media lifecycle, fencing, redaction, recovery, cleanup invariants | all fifteen assigned auditfix slices implemented and native-combined tests pass; complete synthetic media/lifecycle, application-owned resources and final operational gates remain pending |
| 837–873 | Realtime auth/limits/backpressure/replay/gaps/clean shutdown | baseline22send methods/56event literal occurrences retained; dedicated module and complete failure/concurrency matrix pending |
| 876–916 | Middleware ordering, correlation, trusted peers, bounded limiter | frozen order and IPv6 trust-safe fix pass; final application ownership/context/bucket and ordering counterchecks pending |
| 919–974 | Auth/admin/CSRF/SSRF/path/content/secrets/headers/SQL threat boundaries | accepted current-user admin guard reused; adjacent auth tests pass; complete threat/gate review pending |
| 977–1002 | Managed policy-specific HTTP clients, timeouts/pools/retry/limits/errors/close | accepted retry/cache/push source contracts must survive; lifecycle-managed vertical conversion pending |
| 1005–1063 | Structured contextual redacted logging/errors/metrics; four health concepts | existing JSON/request-ID/health retained; full DB/migration/path/tool/key/owner readiness and authenticated diagnosis pending |
| 1066–1120 | Matched before/after performance and resource stability, measured optimizations only | pending; no performance improvement claimed |
| 1123–1198 | Full test categories, ten DB and ten app scenarios, compatibility, meaningful coverage | suite754PASS/13existingSKIP at contract snapshot stage; full final coverage85% modules/nondecreasing repo and scenario matrix pending |
| 1201–1255 | Every blocking lock/style/type/test/coverage/PG/security/image gate truthful | intermediate configured checks pass; full exact-head CI publication and all scan gates pending |
| 1258–1289 | Locked nonroot native runtime, signals, paths, tools, labels, health, no secrets | intermediate native images/HTTPS/PG/restart/identity pass; final matched image size/security/static/PWA/shutdown reruns pending |
| 1292–1330 | Every explicit hotspot genuinely addressed, not merely relocated | database policy fixed; remaining architecture/supervision/private coupling/import/I/O/model/typing hotspots pending |
| 1333–1409 | Complete architecture/lifecycle/database/security/quality/compatibility/operations DoD | NOT yet met; row-level final evidence must close every local obligation |
| 1412–1465 | Reviewable commits, complete DraftPR body, exact head/base/CI, no partial delivery | commits ongoing; no DraftPR/final CI/independent review yet |

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

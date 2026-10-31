# Backend modernization execution ledger (#842)

## Binding and authority

Repository/push/PR: `Serph91P/StreamVault`; base `develop@36e968774bb41b222296a75b3a406c0be385badd`; branch `refactor/842-remaining-modernization`. Exactly one writer in the assigned worktree. No merge, release, deployment, production access, real provider credentials, history rewriting or new infrastructure.

The complete 1,465-line `canonical-842-request.txt`, original issue, current owner comments and `backend-audit.md` govern this plan. The old #847 plan is historical, not an integrated deliverable. Max's later decision supersedes active Twitch priority/preemption/handoff and the proposed 0..1000 change; preserve dormant code/data and ordinary ownership, fencing, budgets and anonymous fallback. Existing packaging, persisted keys/JWT, atomic refresh, supervisor, category async slice and Alembic bridge must be verified and reused, not replaced.

## Execution sequence and acceptance

1. Freeze the actual base contracts: OpenAPI, composed routes/middleware, settings names/default expressions (never environment values), schema, WS methods, tasks/jobs/subprocess/path inventories. Record baseline test/quality/security/PG/image/performance measurements. Build the complete source-line-to-evidence matrix before broad refactoring.
2. Read published predecessor deltas (#933/#900 and #937/#939/#940/#943/#945/#958/#960/#962/#963/#964/#967/#968); preserve their public seams and exercise their exact combination in an isolated test area. Never require an unauthorized merge or edit another worktree.
3. Correct each independent audit bug (#938/#941/#942/#944/#951/#952/#953/#954/#955/#956/#957/#959/#961/#965/#966) with its own observed failing regression and small commit. Keep discovery read-only, media ownership authoritative, cleanup truthful, shared/isolated queue contracts identical and finalization outside the global registry lock.
4. Prove production missing-database RED outside pytest; remove implicit SQLite/pytest policy while preserving explicitly injected SQLite tests. Bump only Streamlink to 8.6.3, retaining urllib3 2.8.0 and the accepted http-ece dependency/export; reproduce native HTTP request preparation offline before and after.
5. Isolate construction from runtime: pure settings/factory/imports, app-owned injectable services/database/HTTP/tasks, explicit post-migration identity bootstrap, existing `app.main:app` and public routes preserved. Move composition out of the entry point. Verify concurrent distinct app instances and cancellation/critical/optional startup.
6. Complete documented DB I/O and typed feature-model boundaries vertically without schema/history changes. Do not cross session/task boundaries with ORM objects or run blocking SQL/filesystem/network on the event loop. Preserve accepted category/Alembic contracts.
7. Complete supervisor/recovery/drain/cancel/reap, managed service-specific HTTP policies, readiness/startup/liveness/admin diagnostics, structured contextual/redacted errors/logging and existing security/EventSub/WS/HLS contracts.
8. Execute genuine PG empty/current/legacy/interrupted/concurrent/restart/outage/key/refresh/recording-after-migration scenarios, matched performance/coverage, Docker HTTPS-health/build identity/static/PWA/shutdown smoke, scanners, Compose and affected REAL/MOCK browser gates. New/substantially rewritten modules need meaningful >=85% coverage; repository coverage must not regress. No gate/skip/threshold weakening.
9. Publish small Conventional Commits and a Draft PR against develop with Refs #842 and #834, exact base/head, subsystem changes, complete criteria evidence and current exact-head CI. Same-card independent review by developer-reviewer. External physical-device/authenticated-provider acceptance remains explicitly with Owner; locally unmet MUSTs do not qualify as completion.

## Shared interfaces / preflight

- #951/#952/#957/#938/#953: discovery/adoption, active/dead identity and cleanup safety share persisted recording/stream state. Separate bugfixes before moving architecture.
- #954/#955/#965/#961: queue handler arity, outcome, retry and external capture heartbeat share worker/manager state. Preserve dependency failure semantics and cancellation.
- #956/#959/#961: local child identity, lease fencing and per-recording serialization must agree; slow media work cannot hold global registry locks.
- #937/#939/#966: preserve admin guard, 401/403/CSRF and existing path ownership while repairing the actual mounted recovery route.
- #940/#962/#967/#958: reuse accepted encryption, atomic file publication, optional startup failure and bounded auth/retry contracts during HTTP/factory refactoring.
- #933/#960/#963: preserve effective codec/quality and duration_minutes wire contracts during process/lifecycle work.

## Rollout and rollback boundaries

No rollout is executed by this task. Operator must back up the PostgreSQL database and persistent recordings/config/key volumes before an authorized upgrade. Validate the candidate against a restored isolated database first. Existing migrations remain canonical; architecture-only changes require no schema migration. Roll application image back to the preceding pinned digest with the same persistent volumes when no irreversible database migration has occurred. Never rotate/recreate identities to resolve startup errors. For database recovery, stop writers and restore a verified matching backup under separate operator authorization; do not blindly downgrade historical migrations. Individual source changes are reversible with ordinary forward revert commits, never reset/force-push shared history.

## Observed progress (not completion)

- Exact live develop and clean assigned branch verified at the bound base.
- Complete original source, provenance, issue including current supersession comment, historical reconciliation and current audit read.
- Locked environment created with CPython 3.14.7. Fresh base `pytest tests/ -q --cov=app --tb=short`: **630 passed, 13 existing opt-in skips, 90 warnings, 2 subtests**, 50.76s. Raw coverage: 27,647 statements / 18,056 missed / 7,506 branches / 521 partial branches; reported combined coverage 31%. Raw JSON/log retained in task scratch, not confused with a final pass.
- Base CI commands: Ruff app PASS; explicit py313 formatter 189 files PASS; configured mypy five files PASS; lock PASS; CI Bandit filter PASS. Broader scans remain separately reported.
- Graphify 0.9.92 isolated tracked-code graph built; `create_app` query resolves `app/main.py:L120`. Serena 2.0.0 scoped to the exact worktree, supervisor symbols retrieved. Graph coverage is the declared suffix/recognized-shell scope, not whole-system semantic proof.
- Historical default card IDs returned not-found on board default; no old card was reopened or altered. Their surviving source/review artifacts remain available; missing history is not an excuse to skip the current acceptance.

All implementation, full matrix, runtime/PG/image measurements and final gates remain pending at this ledger entry.

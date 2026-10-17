# Backend modernization migration plan

Start from `develop@99b101f8fe140fc897eb53a4d80895a660f3025e`. Every package is
a small reviewed PR to `develop`, references #842, has one writer and performs
a semantic diff against the P0 contract snapshot. No history rewrite, force
push, production connection, credential handling, deployment or release is
part of this plan.

## Completed evidence and P0

- #846 supplied an application-factory seam and is baseline evidence only.
- P0 freezes current OpenAPI path/methods, composition order, WebSocket event
  method names, environment names/defaults, services/jobs/subprocess kinds and
  persistent paths. It records the non-reproduced develop Playwright focus
  failure without changing UI behavior.

## Ordered implementation slices

1. Integrate #834 through its existing #836 branch by normal forward
   integration; do not create a competing implementation.
2. Add deterministic packaging/lock workflow and remove `.env` from the index
   with placeholders and credential-rotation warning (no history rewrite).
3. Make settings construction pure and move key bootstrap after migrations.
4. Establish explicit lifecycle/task/process supervision and redaction.
5. Record the DB I/O ADR, then make a low-risk vertical model/session boundary
   slice before any broader model split.
6. Build and prove the legacy-numbered-state to Alembic bridge on real
   PostgreSQL fresh/current/legacy/failure/interrupted/concurrent/restart cases.
7. Modernize API/Realtime/Middleware/HTTP security in bounded slices; split if
   router/WS and HTTP/security collide on hotspot files.
8. Implement #841 backend scheduler after #834, lifecycle and migration
   foundations; then its UI against the frozen backend contract.
9. Run final synthetic acceptance, matched performance/coverage, Docker and
   operator documentation pass.
10. Run the #841 live-media canary only after explicit external authorization.

## Required evidence per slice

- Start from the current live `develop` ref and record base/head SHA.
- Add or adjust tests before production behavior; preserve contract assertions.
- Run the relevant focused tests plus backend coverage, Ruff lint/format,
  bounded CI mypy, frontend lint/type/build/browser tests and `git diff --check`
  where executable. Record concrete blockers rather than fabricating passes.
- Require real PostgreSQL tests for DB/migration/scheduler slices; local SQLite
  success does not prove them.
- Review the contract delta for removed APIs, environment aliases/defaults,
  middleware order, WebSocket event shapes, subprocess types and persistent
  paths. A compatibility break needs an approved adapter/migration/deprecation
  plan.

## Rollback model

P0 itself is additive documentation/fixture/test work and reverts as one commit.
Later runtime slices must have independently reversible commits, migration
preconditions and operator backup/recovery instructions before they modify
persistent behavior. Never use snapshot regeneration to mask an unreviewed
runtime regression.

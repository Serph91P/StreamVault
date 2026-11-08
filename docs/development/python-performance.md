# Python performance candidate (#1045)

This is a **local, uncommitted candidate**, not an independently approved release
or a deployment. The functional gates and repeated measurements below ran against
synthetic local data. Provider operation, a real 24-hour soak and production sizing
are not implied. The legacy API remains compatible; Vue uses bounded reads.

## Resource and consistency boundaries

- Recording/live children drain stdout and stderr immediately through one owner.
  Each pipe retains at most 64 KiB of redacted diagnostics. Overlong lines are
  discarded whole; early authentication/error classifications survive tail
  rotation. Cancellation of a consumer does not cancel the drain owner.
- Streamlink defaults to `info`; existing `LOG_LEVEL=DEBUG` still opts in.
  Credential-bearing raw child logs remain disabled.
- Active-recording cache misses use worker-owned sessions and three batch queries
  instead of one plus two per recording. Media preparation and queue status reads
  return values rather than live ORM rows across worker boundaries. Authentication
  sessions close before slow bodies. The one-slot-pool setup route still works.
- Background admission persists a dependency chain before acknowledging it. A
  bounded dispatcher keeps deferred backlog in the database, not per-stream Python
  queues. Negative handler results fail; retry/backoff and final dependency failure
  work in shared and isolated modes. Terminal retention keeps 1,000 recent rows,
  retires at most 100 per pass and protects nonterminal dependencies. Admission,
  claims and retirement share a short transaction boundary.
- Two process-wide heavy-media slots and four separate probe slots cover the normal
  post-processing launch paths. Capture/live starts bypass these budgets. Slots
  remain held until children and pipes are reaped, including cancellation during
  launch. Journal claims also coordinate peer-store execution capacity.
- On Linux, media children use a parent-death exec shim. Queue ownership additionally
  uses persistent UUID markers and inherited `flock` descriptors. Recovery requires
  positive release/death evidence, not an elapsed TTL. Missing, unreadable or
  unsupported markers remain unknown. A bounded periodic recheck handles delayed
  release of inherited descriptors.
- **Keep owner markers on the same persistent, shared, reliably flock-capable
  storage domain for all participating workers.** PostgreSQL alone does not make
  unrelated local marker directories a distributed lock. This is not a cross-host,
  NAS or non-Linux crash-acceptance claim.
- Retried remuxes write target-local owned scratch, validate it and atomically
  publish the MP4 before recording step completion. Error/cancel preserves the
  source and existing final file. Bounded scratch cleanup needs a positive old-owner
  lock proof. There is no global scratch deletion.
- Segmented finalization stages concatenation in its own segment directory and
  resolves the final collision before admitting one processing chain. It does not
  move a file onto a `_copy1` of itself. The lifecycle monitor waits for the active
  finalizer; real unrelated target files remain protected. Stop, rotation and
  natural completion share the existing per-recording ownership lock. Both normal
  stop and timeout/SIGKILL release the global process-registry lock before waiting
  for finalization/heavy admission. The segmented owner stays visible until that
  work ends; duplicate stops wait for the same owner, not a second publisher.
  Cancellation before child exit retains the live owner; cancellation while waiting
  for heavy admission preserves on-disk inputs for recovery.

Small existing modernization fixes are reused, not claimed as new discoveries:
`d5b5bdce` (#954), `eea67f69` (#955), `bdd0de27` (#965), `e2f8efb0` (#961),
`543fc306` (#952), `c966fa4e` (#959), the worker boundary from `19b69390`, and the
required closed startup-snapshot/fencing slice from `a34aaf69`. This does not import
its factory/actor/owned-HTTP architecture, add dependencies or rewrite the backend.

## Indexed video API and Vue callers

The legacy `GET /api/videos` array is retained. `GET /api/videos/catalog` adds:

- `page` (1-based), `page_size` (1–100, default 50)
- literal case-insensitive `q`, `streamer_id` or `streamer`, `category`, `recording`
- `sort=date|title|streamer|duration|size`, `order=asc|desc`
- offset-aware `created_from` inclusive / `created_before` exclusive
- `duration=short|medium|long` at the existing one-/three-hour boundaries

SQL performs filtering, order, count and limit/offset, with stream ID as the stable
secondary order. The response contains `items`, `total`, `page`, `page_size`,
`has_more`, global `summary` facets/totals and explicit `index` freshness/errors.
`GET /api/videos/{stream_id}/metadata` opens a player without a whole-catalog read.
Interactive identity is required; API keys do not grant browser-media access.
REAL/MOCK transports and library/home/player callers are migrated. Selection resets
on page/filter changes; failed partial-delete survivors are checked by metadata.

Alembic revisions `20261105_catalog` and `20261106_tasks` add a filesystem read
model and durable work tables. Reconciliation is bounded, worker-owned and outside
requests. Source mutations mark existing snapshots dirty transactionally without
hiding valid media. Newly eligible streams receive a pending snapshot in that same
transaction, even behind the discovery cursor. Priority lookup uses indexed
state/dirty metadata; normal discovery keeps an ID cursor. A primary-key join avoids
starvation from orphaned legacy SQLite snapshots. There is no full-library priority
scan before every batch and no TTL increase to conceal maintenance work.

Heartbeats alone do not invalidate media. Optimistic revisions reject stale source
writes. Unchanged batches update only one bounded `checked_at` stamp, not metadata
or revisions. These stamps and their index still have a measured storage cost.
Availability and size/duration order describe the indexed snapshot, not a global
filesystem transaction. Active page values are best-effort current values. Bounded
page-path revalidation refills once; a second change or revision conflict returns
HTTP 409 for bounded refresh, not a stale write or a silently empty success.

ID/public-ID media delivery uses installed Starlette range/HEAD handling with a
finite full-response snapshot. Growing captures cannot outgrow Content-Length.
Auth/share/path/API-key checks remain. Legacy streamer/filename and filename-only
compatibility routes retain their manual 8 KiB generators and the previously audited
shadowing limitation; current frontend/API wrappers use the ID path. This is not a
claim that every backend 8 KiB loop was removed.

## Repeated local measurements

All values below are medians of three per-run values. No host cache flush occurred.
CPU includes co-located clients/background work. Lifetime RSS includes fixture
seeding/index construction; tree-RSS samples may count shared pages twice.

### Final catalog cohort

The same harness exercises five sort modes, pages 1–3 and alternating search across
10k/50k synthetic entries at concurrency 1/8. There are 24 cells and 720 measured
responses. Native background reconciliation is included. Identity is overridden in
this ASGI resource harness; real auth/TCP/browser checks are separate.

| Entries / clients | CPU s per 30, old → new | Request p50 ms, old → new | Lifetime RSS MiB, old → new |
|---|---:|---:|---:|
| 10k / 1 | 12.275 → 0.779 | 396.972 → 19.989 | 170.652 → 145.133 |
| 10k / 8 | 12.265 → 1.734 | 3,078.180 → 113.758 | 211.676 → 167.656 |
| 50k / 1 | 61.802 → 2.717 | 1,987.090 → 84.996 | 313.117 → 148.461 |
| 50k / 8 | 61.779 → 5.129 | 16,071.580 → 262.631 | 467.297 → 178.746 |

This intentionally compares legacy arrays of 9,900/49,500 items with pages of 50,
not equal-sized payloads. At 50k/c1, old/new response totals are 541.272/0.632 MiB.
The first candidate index costs another 6.715 wall seconds / 3.905 CPU seconds on a
warm shared fixture file, excluded from the request window. It is not an OS/NAS
cold-cache result. Static active rows and one shared file are not growing captures
or filesystem-breadth acceptance.

**No general I/O win:** final 50k/c1 global SQL is 90 → 567, logical read bytes
444,458,520 → 2,978,336,816, and kernel-accounted writes 0 → 6,004,736 bytes.
Kernel read bytes are zero for both in warm cache. Candidate reconciliation covers
a median 6,600 rows during that window. Global SQL is not a per-request N+1 count.

### Native reconciler idle cost, 50k / 75 seconds

Each of three candidate windows completes an actual 50,000-row cycle: 251 batches,
2,252 SQL statements. This is the native reconciliation loop, not the entire idle
application. Baseline has no equivalent readmodel maintenance.

| Metric | Baseline | Candidate before discovery fix | Final candidate |
|---|---:|---:|---:|
| CPU seconds / 75s | 0.299 | 8.222 | 6.491 |
| Logical read bytes | 249,754 | 4,611,391,680 | 24,283,848 |
| Kernel-accounted writes | 0 | 45,215,744 | 45,215,744 |
| Kernel read bytes, warm cache | 0 | 0 | 0 |

The old priority full scan is fixed and remeasured, not merely documented away.
Persisted freshness maintenance still costs writes and CPU. Old and new cohorts
remain separate; this is not a zero-cost cache or a universal storage saving.

### Capture, real processing and authenticated TCP playback

The completed mixed cohort uses 1/4/8 real local capture children for 120 seconds,
16 MiB combined stdout/stderr per writer, real registered processing handlers on
separate six-second clips and byte-checked full/range/slow HTTP playback. It is not
Twitch, app lifespan or sustained 120-second transcoding. Capture output is separate
from the processing fixture; the integrated test below covers that ownership flow.

At four channels, three-pair medians are app CPU 107.729 → 80.271 seconds, sampled
app RSS 315.242 → 241.828 MiB, completed transfers 1,586 → 3,475 and p95
424.164 → 117.229 ms. More HTTP work completes, so these are not equal-work CPU or
I/O comparisons. At one channel there is no general CPU/RSS improvement.

All three eight-channel baselines fail with ReadTimeout at pool peak 15/15. In the
first pair, all eight saturation stacks show synchronous main-loop pool wait in
`_dependency_worker` → `_do_get`, with an auth worker also waiting. Connections
balance after drain: this is starvation/blocking, not a demonstrated permanent leak.
The candidate completes all three runs and all 40 unique accepted IDs per run,
validates full 120-second captures and limits sampled heavy FFmpeg peak to two.
No speedup is computed against zero successful baseline transfers.

**I/O correction:** Linux `/proc/PID/io` already includes waited children. Old
mixed/collector sums of root and child peaks can double-count and miss exits;
these raw fields are diagnostic only. A separate three-pair C4/120s observer measures
root-only deltas after drain/wait, before final probe/decode/temp cleanup:

| Metric | Baseline | Candidate |
|---|---:|---:|
| Kernel-accounted write bytes | 474,947,584 | 476,336,128 |
| Cancelled write bytes, separate | 98,304 | 98,304 |
| Kernel read bytes, warm cache | 0 | 0 |
| Logical rchar bytes | 5,432,003,133 | 10,567,499,900 |
| Completed transfers | 1,561 | 3,341 |
| Validated HTTP bytes | 4,169,158,688 | 9,231,916,908 |

No I/O gain is claimed. These are process-attributed counters including client,
observer and waited children, not device totals or a completed-writeback guarantee.
The last catalog-only correction does not silently rebind these earlier mixed
runs to an identical whole-source snapshot. Queue/recorder/media/auth code is
unchanged; final catalog/idle runs and the new integrated test cover the changed
catalog code. Raw source manifests remain distinct.

### Output and Streamlink buffer comparisons

Three collector pairs each run four genuine six-second FFmpeg captures and 32 MiB
combined output per writer. CPU is 3.606 → 3.471 seconds, wall time 7.820 → 5.812,
sampled app RSS 245.488 → 120.094 MiB and retained output 134,217,728 → 524,288
bytes. All 24 capture reports are hash-identical and fully decodable. Early CPU
regressions remain historical; the newest three micro-pairs do not establish a
universal CPU-neutral or long-soak claim. Collector I/O is diagnostic only.

The installed Streamlink 8.6.0 HTTPStream/RingBuffer comparison has 27 cells and
117 byte/hash-correct 64 MiB streams at 32/128/512 MiB and 1/4/8 readers, including
slow readers and producer pauses. At eight streams, median RSS is
304.598/367.328/371.699 MiB and wall time 4.577/4.535/4.528 seconds.
Smaller buffers trade memory for CPU/backpressure. A 64 MiB input does not fill a
512 MiB ring and does not prove WAN/HLS segment-loss tolerance. **The existing
512M CLI default remains unchanged**; no optimal-buffer claim is made.

## Stop-admission review correction

Independent review found that the first stop could hold the global ProcessManager
lock while waiting for two busy heavy-media slots, preventing a peer capture from
receiving SIGTERM. The correction above changes only that ownership boundary, not
media/timeout budgets or admission semantics.

`tests/test_recording_stop_admission.py` first reproduced both stop branches as red
with two real FFmpeg slot holders and two writing FFmpeg captures. Its seven cases
now pass, including timeout/SIGKILL, simultaneous natural monitor/duplicate stop/
rotation, cancellation and intact one-time finalization with FFprobe/full decode.
Separate small boundary cases preserve a live owner on early cancellation, retain
inputs/replacement identity after a finalizer failure, and persist the final path
for callback-admission retry in a fresh SQLite session/orchestrator. That last case
controls the queue-admission failure/acceptance; it is not a process-crash test.
The unchanged original review probe also passes after the fix.

Fresh native SQLite/PG17 gates pass: 111 target cases, nine full-stack cases and
one actual app/PG restart case (101.35s), retaining the two SIGKILL windows and
five recovered plus six new capture-chain job IDs. The complete backend gate is
also rerun for this correction; exact results and source binding are in the local
handoff. Frontend/build/browser and performance cohorts below are the earlier,
independently reviewed evidence, not silently relabeled reruns after this Stop-only
change. No frontend source, dependency, existing assertion, timeout or budget changed
in the correction. Production/long-soak limits remain below.

## Executed pre-correction gates and real user flows

These counts overlap and must not be added:

- Native whole backend: **1,241 passed, 71 opt-in skips, two subtests**, 384.56s.
- Unchanged full SQLite/PostgreSQL target slice: **111 passed, no skips**, 100.51s,
  with explicitly owned tmpfs SQLite fixtures and real PG17. Two additional native
  target runs each had 110 passes/one SQLite timing failure: a 100-job stop/start
  deadline and a five-second `BEGIN IMMEDIATE` lock timeout. Accepted unfinished
  work remained durable; the exact first case then passed unchanged in 8.91s.
  Fail logs remain evidence. No assertion, timeout, pool or pragma was relaxed;
  tmpfs success is not presented as native storage-performance acceptance.
- Canonical empty/legacy/interrupted/concurrent/restart PG migration and the new
  dirty index pass; independent SQLite/PG index/sentinel checks also pass.
- Native full-app PG gates: **eight passed** for real middleware/auth/CSRF,
  websocket replay, share/range/expiry, settings and readiness.
- New integrated restart test: **one passed, 99.49s**. Two actual app SIGKILL
  windows (during FFmpeg and after MP4 publication but before step commit), a real
  PG service restart and the same five recovered IDs. A separate 45-second live
  capture survives. A real RecordingManager then captures 12 seconds, through all
  six production steps and cleanup under 50k/c8 catalog load: exactly six journal
  rows/RPS IDs, no owned TS/copy leftovers, released lease/reaped child, complete
  MP4 decode and a stable final 200 catalog page. No power-loss/exactly-once claim.
- Real REAL-Vue/browser/PG/FS/auth checks pass: desktop/mobile viewports, pages
  50/50/20, search/global filters/sort/history, metadata-only deep player, play/seek,
  actual deletion and targeted real DB-failure partial deletion with durable
  survivor checks. Independent coverage uses matching Playwright 1.63/Chromium153.
  The final REAL build has identical verified runtime bytes. A fresh final run
  against the current backend also passes in 24.39s with exact pre/post source and
  REAL-provenance hashes; its browser uses matching Playwright1.63/Chromium153 in
  an owned disposable container (Node24.20.0; build/unit gates use24.22.2).
  A mobile viewport is not Android acceptance, and screenshots are not
  pixel-visually approved.
- Real PG/TCP media auth/range/HEAD checks, a separate actual SQLite expired-share/
  one-slot-pool slow-body check and growing-file TCP framing checks pass. The latter
  stub DB/auth/path only, so these are not misrepresented as one end-to-end check.
- Ruff/201 canonical app files and CI-configured mypy/five files pass.
- Node24.22.2 locked install, lint/token/foundation/typecheck pass; **684 unit tests
  pass with four mode-specific skips**, those four separately pass in MOCK mode;
  **49 foundation tests pass**. Clean-build output, REAL/MOCK provenance, precache,
  loading and output-budget gates pass. Existing lint warnings and 20 lock audit
  findings (two low/eighteen moderate) remain; no dependency/audit-fix scope added.

The original bundle gate was red. The same-lock MOCK feature increase is
4,970 JS bytes / 1,642 gzip bytes. Max explicitly approved only
`budgets.jsBytes:1196533→1201533` and `budgets.jsGzipBytes:381000→382700`.
The existing product-boundary fixtures were then explicitly authorized to follow
those limits: gzip boundary/+1 and oversized application 1,201,534 bytes.
Expected statuses/assertions, the separate historical budget fixture, HLS allowance,
validators and all other budgets stay unchanged. Final measured application JS /
gzip is MOCK 1,201,391 / 382,622 and REAL 1,196,367 / 380,949. Old red evidence is
retained. This is not permission to publish, merge or deploy.

## Reproduction and limits

Use the selected checkout's locked Python and disposable synthetic storage only:

```sh
python tests/performance/catalog_benchmark.py \
  --repo /path/to/checkout --entries 50000 --concurrency 8 --repeats 30 \
  --endpoint '/api/videos/catalog?page_size=50' --output /path/to/catalog.json
python tests/performance/catalog_benchmark.py \
  --repo /path/to/checkout --entries 50000 --concurrency 1 --repeats 1 \
  --idle-seconds 75 --endpoint '/api/videos/catalog?page_size=50' \
  --output /path/to/idle.json
python tests/performance/mixed_media_benchmark.py \
  --repo /path/to/checkout --channels 8 --seconds 120 --output /path/to/mixed.json
uv run pytest -q
uv run ruff check app/
uv run ruff format --check --target-version py313 app/
uv run mypy
```

PostgreSQL tests require explicitly named loopback `streamvault_test_*` fixtures;
full-app/restart gates additionally enforce disposable user/database/container
ownership. Never point them at an existing application database. The artifact
handoff retains exact controller argv, raw JSON/CSV, source hashes, failed runs,
commands and cleanup state.

Not run: production/provider operation, WAN/NAS cold cache, real 24-hour/multiday
soaks, Windows/Android/macOS, cross-host/network-filesystem locking guarantees or
pixel screenshot review. Repeated 120-second children and accelerated/dated
2h/8h boundary fixtures are not real 2h/8h/24h soaks.

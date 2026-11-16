# Backend #842: matched measurements

## Scope and provenance

**Local B4 correction measurement complete; independent correction review remains required.** Measured on 2026-11-13 against runtime source `7465aba4e9d04de26b50c60f596ba891806d580c`, after the ProcessManager finalizer/segment work and the live-playlist filesystem worker correction. Base is `49b61a80962e249789c2836db301e9fa9f305b3e`. The later integrated develop frontend-only PR1069 inputs remain in the candidate; backend baseline selection is unchanged. Earlier cf30/c63 comparisons are historical, not members of this aggregate. Repeat measurements if product behavior changes.

Three fresh base/candidate pairs ran serially, alternating base then candidate, without competing own tests/builds. Both source-built no-push images have identical CPython3.14.10, all75 installed runtime distributions, all147 installed APK package/version pairs and their four OS base layers. This is not Python3.14.7 evidence. The candidate's additional typing-only lock entry is not asserted to make the complete uv.lock byte-identical. Two preliminary APK-mismatched images were rejected before these runs: a genuinely uncached base rebuild restored runtime parity, not a product dependency or threshold change.

Immutable runtime image IDs:

- Base: `sha256:363c68824a5cda5ed27eee7b026a82a4456c3b8a2604b72b6cd18e40a3caf7c7`.
- Candidate: `sha256:57f50c185227fdb97eb22705e937f6332e47d056fdebe723b62be9a2fde81e9e`.
- Each of the six actual PostgreSQL containers was inspected: all use `sha256:c293117fcecda7344b5480222e813b9f673d7abd69b1dd95eff239b768b04f59`, PostgreSQL18.6. This is now per-container evidence, unlike the historical c63 tag-only inspection.

Every result retains image inspection, exact source head, identical three harness hashes, raw samples, profiler records and cleanup. The only harness addition records the actual PG container image before workload timing; workload, assertions and budgets are unchanged. Each execution creates an owned `--rm` fresh tmpfs PG container, then a normally migrated app/lifespan in that container's `--network none` namespace. No published ports, external provider, production database/volume/key or shared service. Benchmark entry/client are copied into the disposable container, not the product entry point. Docker arguments/resource settings match. This is shared-host measurement, not dedicated-CPU or statistically significant capacity certification.

```sh
python tests/performance/run_backend_comparison.py \
  --image streamvault-842-benchmark:base49-matched-7465aba-nocache \
  --source-head 49b61a80962e249789c2836db301e9fa9f305b3e \
  --output <new-empty-base-output>
python tests/performance/run_backend_comparison.py \
  --image streamvault-842-benchmark:candidate-7465aba-matched \
  --source-head 7465aba4e9d04de26b50c60f596ba891806d580c \
  --output <new-empty-candidate-output>
```

Repeat the pair three times without competing tests/builds. Correction evidence contains `842-performance-7465aba-{base49,7465aba4}-{1,2,3}/`, the runner log, `842-performance-7465aba-{runs,summary,final-provenance}.json`, and the executable `run_final_performance.py`/`summarize_final_performance.py`. All six results passed, as did all twelve owned-container removal checks. Report SHA256s and harness hashes are in the aggregate. Historical results are not pooled here.

## Workloads and results

The common fixture has20 synthetic streamers and2,000 recorded streams; catalog pages must contain the requested50 items. Authentication uses real setup/login and a synthetic local user. Each fresh process uses the same seed/order, one warmup and30 timed reads per endpoint. Tables pool **90 observations per variant**; p95 is the sorted sample at `int((n-1)*0.95)`, not interpolation. Query counts/times are actual SQLAlchemy driver events including workers, not estimates.

| Actual HTTP read | Base median / p95 ms | Candidate median / p95 ms | Base / candidate SQL count | Base / candidate median SQL ms |
| --- | ---: | ---: | ---: | ---: |
| `/api/health/live` | 1.201 / 1.316 | 1.237 / 1.676 | 0 / 0 | 0 / 0 |
| `/api/recording/active` | 3.204 / 5.388 | 3.374 / 5.170 | 3 / 2 | 0.393 / 0.320 |
| `/api/streamers` | 17.728 / 24.643 | 20.901 / 33.735 | 44 / 43 | 4.313 / 5.105 |
| `/api/videos/catalog?page=1&page_size=50` | 25.552 / 41.245 | 23.006 / 33.889 | 12 / 12 | 12.951 / 11.418 |

Other samples also pool90 observations per variant:

| Workload | Base median / p95 ms | Candidate median / p95 ms |
| --- | ---: | ---: |
| Native WS send → subscribed socket receive | 3.096 / 4.035 | 3.015 / 5.171 |
| HMAC-signed EventSub challenge → acknowledgment | 1.715 / 3.339 | 1.754 / 2.286 |
| Native synthetic Python child start + terminate + wait/reap | 18.895 / 26.418 | 17.485 / 25.357 |

Medians of three independent runs:

| Measurement | Base | Candidate | Observed change |
| --- | ---: | ---: | ---: |
| Container start → first HTTP liveness, seconds | 4.705379 | 4.907112 | +4.29% |
| Post-startup RSS before workload, KiB | 172268 | 170292 | −1.15% |
| Docker image bytes | 719388752 | 719587496 | +0.03% |
| 100 native queue handler completions, jobs/second | 54.410286 | 56.759082 | +4.32% |
| Recording actor admission → acknowledged child, seconds | 0.154739 | 0.134353 | −13.17% |

Image-size differences include accepted frontend inputs, not just backend code. The recording workload uses the real recorder/actor/admission/config/lifecycle/ProcessManager; only the provider executable is a local Python child acknowledging pid/startup. All six runs verify startup, stop and reap. This is not stream acquisition, codec/provider recovery or authenticated-provider certification. The separate standalone-child workload is not an actor-startup substitute.

Post-workload base FD counts `[25,25,25]`, candidate `[27,26,27]`; base asyncio tasks `[21,21,22]`, candidate `[21,21,21]`. Snapshots include the normal dispatcher, not a leak-slope proof. Separate repeated stability/drain tests remain required.

## Regression assessment and measured hybrid decision

There is **no blanket speedup claim**. Startup, liveness, streamer median/p95/SQL time, active-recording median, EventSub median, WS p95 and image size worsen. Catalog reads, active-recording p95/query count, EventSub p95, WS median, standalone-child samples, queue throughput, actor startup and idle RSS improve here. Listing still has43 statements for20 streamers; catalog retains12. Neither N+1 elimination nor causal attribution of these small-sample differences is substantiated. No gate, individual timeout, drain budget or performance threshold is relaxed.

Each run separately profiles ten authenticated loopback catalog requests in the serving interpreter. Retained `catalog_profile` identifies its event-loop-thread cProfile scope; worker SQL time is measured separately. Profiling perturbs latency and is excluded from timed tables. These observations help inspect projection/auth work; they are not independent CPU accounting or proof that worker SQL executes on the event loop.

Retain the hybrid for **ownership/session/cancellation correctness**, not a global performance advantage. Preserve the integrated category `AsyncSession` slice. Legacy synchronous catalog/file/process units execute as complete app-owned cancellation-drained worker scopes returning scalars/DTOs. ADR-001 records the measured choice and thread/pool/drain costs. No universal async rewrite is justified by this sample. B5/B6, original-probe scope, operational evidence and exact-head CI remain independent gates, not inferred from B4.

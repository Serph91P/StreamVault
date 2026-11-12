# Backend #842: matched measurements

## Scope and provenance

Measured on 2026-11-12, not inferred from resource-stability tests or historical CI. This correction comparison replaces the earlier cf30e625 measurement: base `49b61a80962e249789c2836db301e9fa9f305b3e` versus product source `c63b1aa2208259f010dbcda57c175ab8dadcbb82`. It includes the later app-owned retention/admin/queue/recovery/lifecycle corrections and the recording-progress DAO lookup; the earlier results are not transferred to these changes. Subsequent test/documentation-only edits are not a new product measurement. The later `ConfigManager`, `async_file` and `StreamlinkConfigService` strict-root additions change only precise annotations (including the existing quality-list local annotation): AST comparison after annotation erasure proves equal bodies/defaults. Actual configuration/lifecycle15cases and file/config/command37cases pass. This is explicitly not a remeasurement of that later source. Repeat candidate measurement if product behavior changes.

Three independent fresh base/candidate pairs ran serially, alternating base then candidate, without a competing test/build workload. Native disposable executions verify the same **CPython 3.14.10** interpreter and 75 equal installed distributions. Backend `uv.lock` remains byte-equal, SHA256 `dfb3bdf91e30f2dd1b695590a9b6ea6954f41c7b597bfc33fd8e6091f7c29a09`. This is not Python 3.14.7 evidence. The normally integrated PR1069 frontend manifest/lock delta remains in the candidate image; it does not invent a new backend baseline or dependency comparison. Image-size change includes those frontend inputs as well as backend source changes.

Source-built, no-push runtime images: base `sha256:074886ec89478dff61991994c78457821be056fd59f4b0ac159c85dae0e1df50`; candidate `sha256:f806c200cf8c4d7a257b98458001a648238b467bb1b8abf8fc603ccb1c3f718b`. Every raw result retains its image inspection, source head, harness hashes and cleanup record. All six harness hash sets are equal. Runtime/package equality and report hashes are retained separately in `842-performance-r2-provenance.json`. All six actual PostgreSQL logs identify PostgreSQL18.6/Alpine15.2.0. The harness did not retain per-PG-container image inspections; the separate post-run PG tag inspection is not presented as such a record.

Each run creates an owned `--rm`, fresh tmpfs PostgreSQL container, then a normally migrated application/lifespan in that container's `--network none` namespace. No ports are published, no external provider is contacted, no production database/volume/key/shared service is used. The benchmark-only entry/client are copied into the disposable container, not the product entry point. The same Docker arguments/resource settings apply to both variants. This is shared-host measurement, not dedicated-CPU or statistically significant capacity certification.

```sh
python tests/performance/run_backend_comparison.py \
  --image streamvault-842-benchmark:base49 \
  --source-head 49b61a80962e249789c2836db301e9fa9f305b3e \
  --output <new-empty-base-output>
python tests/performance/run_backend_comparison.py \
  --image streamvault-842-benchmark:candidate-c63b1aa \
  --source-head c63b1aa2208259f010dbcda57c175ab8dadcbb82 \
  --output <new-empty-candidate-output>
```

Repeat the pair three times without competing tests/builds. Raw artifacts: `842-performance-r2-{base49,c63b1aa}-{1,2,3}/`, `842-performance-r2-runner.log`, `842-performance-r2-summary.json`, `842-performance-r2-provenance.json`, and the executable aggregation script `842-summarize-performance-r2.py` in correction evidence. All six results report passed; all twelve owned-container cleanup checks pass. Historical cf30 reports remain historical, not members of this aggregate.

## Workloads and results

The fixture has20 synthetic streamers and2,000 recorded streams; catalog pages must contain the requested50 items. Authentication uses real setup/login and a local synthetic user. Each process starts with a fresh catalog, common seed and request order, then one warmup and30 timed reads per endpoint. Tables pool **90 observations per variant**; p95 is the sorted sample at `int((n-1)*0.95)`, not interpolation. Query count/time come from actual SQLAlchemy driver execution events, including workers, not query estimates.

| Actual HTTP read | Base median / p95 ms | Candidate median / p95 ms | Base / candidate SQL count | Base / candidate median SQL ms |
| --- | ---: | ---: | ---: | ---: |
| `/api/health/live` | 1.261 / 1.957 | 1.659 / 3.803 | 0 / 0 | 0 / 0 |
| `/api/recording/active` | 3.895 / 5.915 | 3.513 / 5.454 | 3 / 2 | 0.497 / 0.327 |
| `/api/streamers` | 20.350 / 32.542 | 25.398 / 34.346 | 44 / 43 | 5.276 / 6.690 |
| `/api/videos/catalog?page=1&page_size=50` | 28.008 / 42.890 | 25.699 / 41.279 | 12 / 12 | 14.104 / 12.900 |

Other samples also pool90 observations per variant:

| Workload | Base median / p95 ms | Candidate median / p95 ms |
| --- | ---: | ---: |
| Native WS send → subscribed socket receive | 3.495 / 7.835 | 3.174 / 7.689 |
| HMAC-signed EventSub challenge → acknowledgment | 1.751 / 2.945 | 1.778 / 3.784 |
| Native synthetic Python child start + terminate + wait/reap | 19.891 / 28.185 | 20.986 / 27.918 |

Medians of three independent runs:

| Measurement | Base | Candidate | Observed change |
| --- | ---: | ---: | ---: |
| Container start → first HTTP liveness, seconds | 5.099675 | 4.518302 | −11.40% |
| Post-startup RSS before workload, KiB | 168532 | 172792 | +2.53% |
| Docker image bytes | 719388752 | 723099217 | +0.52% |
| 100 native queue handler completions, jobs/second | 52.986632 | 48.929990 | −7.66% |
| Recording actor admission → acknowledged child, seconds | 0.141085 | 0.143169 | +1.48% |

The recording workload uses the real app recorder, actor/admission/config/lifecycle/ProcessManager. Only the provider executable is replaced by a local Python child acknowledging its pid and expected startup signal. All six runs verify startup, stop and reaping. This is not stream acquisition, codec/provider recovery or authenticated-provider certification. The standalone child workload is distinct, not an actor-startup substitute.

Post-workload base FD counts `[25,25,25]`, candidate `[27,27,27]`; base asyncio tasks `[22,21,22]`, candidate `[21,21,21]`. These snapshots include the normal dispatcher, not a leak-slope proof. Separate repeated stability/drain tests remain required.

## Regression assessment and measured hybrid decision

There is **no blanket speedup claim**. Candidate streamer median/p95 and SQL time, liveness median/p95, EventSub median/p95, standalone-child median, queue throughput, actor startup, RSS and image bytes worsen. Active-recording/catalog reads and WS samples improve here. Streamer listing still has43 statements for20 streamers; catalog retains12. Neither N+1 elimination nor causal attribution of these small-sample differences is substantiated. No gate, individual timeout, drain budget or performance threshold is relaxed.

Each run also profiles ten actual authenticated loopback catalog requests in the serving interpreter. These retained `catalog_profile` records explicitly identify their event-loop-thread cProfile scope; worker SQL timing is measured separately. Profiling perturbs latency and is not included in the timed tables. These are observations for inspecting projection/auth work, not independent CPU accounting, server profiling or proof that worker SQL runs on the event loop.

Retain the hybrid for **ownership/session/cancellation correctness**, not a claimed global performance advantage. Preserve the integrated category `AsyncSession` slice. Legacy synchronous catalog/file/process units execute as complete app-owned, cancellation-drained worker scopes returning scalars/DTOs. ADR-001 records that bounded choice and its thread/pool/drain costs. No unmeasured universal async rewrite is justified by this sample. Final B5/B6, original-probe scope, operational checks and exact-head CI remain independent and open until their own evidence is complete.

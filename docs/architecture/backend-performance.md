# Backend #842: matched measurements

## Scope and provenance

Measured on 2026-11-12, not inferred from resource-stability tests or historical CI. Comparison: base `49b61a80962e249789c2836db301e9fa9f305b3e` and product source `cf30e6252ebd773d85cda365f93c410d2694e1c7`. Later test/documentation/workflow changes are not changes to the measured `app/**` source. If production source changes, repeat the candidate measurements before final acceptance.

Three independent fresh base/candidate pairs ran serially on the same host, alternating base then candidate. Both used the same Docker base/toolchain and production dependency versions: CPython **3.14.10**, 75 installed distributions, programmatically compared equal. Both `uv.lock` files are byte-identical, SHA256 `dfb3bdf91e30f2dd1b695590a9b6ea6954f41c7b597bfc33fd8e6091f7c29a09`. This is not a claim of Python 3.14.7 execution. The two immutable image IDs, PostgreSQL image inspection, actual container inspection and SHA256 of all three harness files are recorded in every raw `result.json`; all six runs used identical harness hashes.

Each run creates its own `--rm` PostgreSQL 18 Alpine container and fresh tmpfs database, then a normal migrated application/lifespan in that container's network namespace. The namespace is `--network none`, without published ports or external provider access. No production database, volume, key or shared service is used. The benchmark-only entry module and client are copied into the disposable container, not installed in the product entry point. Both images have the same resource settings; this is a shared-host experiment, **not** dedicated-CPU or statistically significant capacity certification.

Reproduce with the same two source-built, no-push images:

```sh
python tests/performance/run_backend_comparison.py \
  --image <base-image> --source-head 49b61a80962e249789c2836db301e9fa9f305b3e \
  --output <new-empty-base-output>
python tests/performance/run_backend_comparison.py \
  --image <candidate-image> --source-head <exact-product-head> \
  --output <new-empty-candidate-output>
```

Repeat the pair three times without a competing test/build workload. Retain all output directories, not only this rounded table. Raw artifacts for this execution are `842-performance-final-{base49,cf30}-{1,2,3}/` plus `842-performance-final-summary.json` and `842-performance-runtime-versions.json` in the correction evidence. Failed earlier harness experiments and single-sample reports are not part of these aggregates.

## Workloads and results

The fixture has 20 synthetic streamers and 2,000 recorded streams; catalog responses must contain the requested 50 items. Authentication is real setup/login and a synthetic local user; no external credentials are involved. Each process starts with a fresh catalog, then the same seed and request order. Read measurements include one warmup followed by 30 timed requests per endpoint per run. The table pools **90 observations** per variant; p95 is the sorted sample at index `int((n-1)*0.95)`, not an interpolated tail estimate. SQL count and elapsed time come from actual SQLAlchemy driver execute events in each request's context, including off-loop work; they are not fabricated query estimates.

| Actual HTTP read | Base median / p95 ms | Candidate median / p95 ms | Base / candidate SQL count | Base / candidate median SQL ms |
| --- | ---: | ---: | ---: | ---: |
| `/api/health/live` | 1.331 / 4.647 | 1.320 / 2.260 | 0 / 0 | 0 / 0 |
| `/api/recording/active` | 3.130 / 3.483 | 3.407 / 10.315 | 3 / 2 | 0.384 / 0.340 |
| `/api/streamers` | 21.104 / 43.378 | 24.105 / 45.838 | 44 / 43 | 5.794 / 6.393 |
| `/api/videos/catalog?page=1&page_size=50` | 28.039 / 51.552 | 23.029 / 34.930 | 12 / 12 | 14.344 / 11.713 |

Other latency samples likewise pool 90 observations per variant:

| Workload | Base median / p95 ms | Candidate median / p95 ms |
| --- | ---: | ---: |
| Native WS send → actual subscribed socket receive | 3.021 / 3.688 | 2.965 / 6.863 |
| HMAC-signed EventSub verification challenge → acknowledgment | 1.696 / 2.514 | 1.758 / 3.261 |
| Synthetic native Python child start + termination + wait/reap | 18.156 / 26.515 | 21.209 / 28.780 |

Medians of the three independent runs:

| Measurement | Base | Candidate | Observed change |
| --- | ---: | ---: | ---: |
| Container start → first successful HTTP liveness, seconds | 4.573824 | 4.628688 | +1.20% |
| Post-startup RSS before incoming workload, KiB | 168416 | 169328 | +0.54% |
| Docker image bytes | 719388752 | 719524109 | +0.02% |
| 100 real native queue handler completions, jobs/second | 46.544602 | 45.901111 | −1.38% |
| Recording actor admission → acknowledged physical child, seconds | 0.148911 | 0.135703 | −8.87% |

The recording workload uses the actual app recorder, actor/admission, config, lifecycle and ProcessManager. Only the provider executable is replaced with a local Python child that acknowledges its pid and emits the expected startup signal. All six runs confirm actor startup, stop, child reaping and cleanup. This is **not** stream acquisition, codec correctness or provider recovery certification. The standalone child workload is deliberately separate and must not be passed off as actor startup.

After the common workload, base FD counts were `[25,25,25]`, candidate `[27,27,27]`; base asyncio task counts `[22,21,21]`, candidate `[21,21,21]`. These are snapshots with the normal dispatcher still running, not leak-slope evidence. Repeated stability/drain tests remain separate requirements. Every run's finally block verifies removal of both owned containers; all six cleanup records pass.

## Regression assessment and measured hybrid decision

There is **no blanket speedup claim**. Catalog latency was lower in this sample, but its SQL count remains 12. Streamer listing still performs 43 statements for 20 streamers, and is slower here; these measurements do not substantiate an N+1 elimination claim. Active-recording median and p95, WS p95, EventSub p95, standalone-child latency and queue throughput also worsen in this experiment. Report them rather than hiding them behind unchanged functional budgets or a selected faster endpoint. Startup/RSS/image differences are small in these three observations; no significance or upper-bound guarantee follows.

Each run additionally captures `cProfile` output around ten actual authenticated loopback catalog requests in the serving interpreter. Example first-pair cumulative observations: base `_read_catalog_page` 0.253s / `list_page` 0.248s; candidate 0.211s / 0.189s. Profiling perturbs latency and is not included in the timed read table. These cumulative snapshots identify catalog projection/DB access and authentication as work to inspect; they are not independent CPU accounting, SQL-server profiling or proof of event-loop residency. The actual driver-duration measurements above and separate worker-thread/session regression tests answer those different questions.

The implemented hybrid is retained for **ownership, cancellation and session correctness**, not because this experiment proves it globally faster. Keep the already integrated category `AsyncSession` slice; synchronous legacy catalog/file/process units execute as complete app-owned, cancellation-drained workers and export only scalars/DTOs. Do not introduce an unmeasured big-bang async conversion merely to improve this table. ADR-001's amendment records this bounded choice and its costs. No performance threshold is changed, no provider/device pass inferred, and B5/full exact-head verification remain independently open until their own evidence is complete.

# Frontend performance baseline

## Measured build baseline

The following came from a fresh Node 24 production mock build at base `c679a1b577e04ccbca1c19689ab19d92f5a214d1`.

| Metric | Observed |
| --- | --- |
| Vite transformed modules | 233 |
| build duration | 2.37 seconds |
| deterministic build contract | passed, 86 emitted files |
| PWA precache | 92 entries, 2644.15 KiB |
| global index CSS | 301.79 kB, gzip 37.75 kB |
| Settings CSS | 135.38 kB, gzip 13.29 kB |
| live player JS | 589.38 kB, gzip 183.89 kB |
| initial index JS | 129.91 kB, gzip 37.89 kB |
| audit | 0 vulnerabilities |

Vite warned that some chunks exceed 500 kB. This is a measured baseline defect B-02, not proof of an end-user performance outcome.

## Reproducible Lighthouse collection and measured results

`npm run test:performance` creates a production mock build and writes raw Lighthouse LHR JSON plus `summary.json` to `test-results/lighthouse` (or `LIGHTHOUSE_OUTPUT_DIR`). The runner measures the mobile Streamers route at 390 by 844 and the desktop home route at 1440 by 900. Each route is collected cold and then warm using an isolated Chrome process while retaining the scenario profile for the warm pass. `summary.json` records the Lighthouse version, score, LCP, CLS, TBT, DOM nodes, request count, byte weight, viewport and cache mode.

The candidate harness was run in the approved digest-pinned Playwright 1.62.1 Noble container with no network, mounts or published ports, `pwuser`, dropped capabilities, `no-new-privileges`, 2 GiB memory, 2 CPUs, 256 PIDs and 512 MiB shared memory. It used Node 24.20.0, Chrome for Testing 151.0.7922.34 at `/ms-playwright/chromium-1234/chrome-linux64/chrome`, Lighthouse 13.4.1 and a loopback Vite preview with `VITE_USE_MOCK_DATA=true`. The raw candidate-bound LHRs and summary are retained in the final evidence archive.

| Scenario | Cache | Score | LCP ms | CLS | TBT ms | DOM nodes | Requests | Bytes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Streamers 390x844 | cold | 0.96 | 2640.36 | 0 | 17 | 357 | 40 | 201304 |
| Streamers 390x844 | warm | 0.99 | 1058.93 | 0 | 106 | 347 | 39 | 18784 |
| Home 1440x900 | cold | 1.00 | 657.94 | 0 | 0 | 401 | 40 | 201304 |
| Home 1440x900 | warm | 1.00 | 291.40 | 0 | 0 | 391 | 39 | 18784 |

These are deterministic mock, loopback lab measurements, not native-device, real-backend, installed-PWA, player or realtime claims. The application-default theme was measured; dedicated dark/light Lighthouse bootstrapping remains separate work.

## Remaining metrics and limits

Native-device metrics, route-transition time, realtime-update cost, player startup and memory are not available in this P0/P1 slice. The baseline establishes the reproducible mock method and records actual LHR values without treating them as approved budgets.

## Performance ledger

| Prompt section/lines | Baseline evidence | Future test/artifact | Status |
| --- | --- | --- | --- |
| measurement 1756-1790 | production build/chunk list and four raw mock LHRs | native, real-backend, player and realtime measurements | captured mock baseline |
| optimization 1792-1823 | route lazy imports and large player chunk observed | route/player code splitting and CSS consolidation verification | pending |
| budgets 1825-1833 | no approved budget yet | baseline-derived budget document and blocking check | pending |
| PWA cache security 1367-1411 | VitePWA config/source inventory | manifest/worker/cache-exclusion contract | pending |
| dependency security 1836-1879 | npm audit zero advisories | repeated locked audit and sensitive-cache review | pending |

The later performance owner must compare like-for-like mock fixture, viewport, cache, network and browser conditions. A smaller bundle does not override accessibility or media compatibility.

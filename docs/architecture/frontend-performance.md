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

## Reproducible Lighthouse collection

`npm run test:performance` creates a production mock build and writes raw Lighthouse LHR JSON plus `summary.json` to `test-results/lighthouse` (or `LIGHTHOUSE_OUTPUT_DIR`). The runner measures the mobile Streamers route at 390 by 844 and the desktop home route at 1440 by 900. Each route is collected first cold and then warm using Lighthouse's simulated mobile Slow 4G and CPU profile or its desktop profile. `summary.json` records the Lighthouse version, score, LCP, CLS, TBT, DOM nodes, request count, byte weight, viewport, cache mode and runner conditions.

The run uses `VITE_USE_MOCK_DATA=true` and a loopback Vite preview server. It does not require a backend or external network. The caller must provide an executable Chromium or Chrome. The default is the Playwright Chromium executable; set `LIGHTHOUSE_CHROME_PATH` when the browser is installed elsewhere. The runner fails before launching Lighthouse with the resolved path and the required override when that browser is unavailable.

The current workflow measures the application-default theme. A dedicated dark/light Lighthouse bootstrap and installed-PWA pass remain separate baseline work; neither has been represented as a completed measurement.

## Unmeasured or blocked metrics

No Lighthouse LCP, CLS, TBT, browser request-count, DOM-node or byte-weight measurements are recorded in this baseline yet. The host used for this evidence has no executable at its configured Playwright Chromium path, so the collection exits with an actionable missing-browser error rather than emitting fabricated metrics. Native-device metrics, route-transition time, realtime-update cost, player startup and memory are also not available on this host.

## Performance ledger

| Prompt section/lines | Baseline evidence | Future test/artifact | Status |
| --- | --- | --- | --- |
| measurement 1756-1790 | production build and chunk list | Lighthouse JSON, browser performance entries, bundle report | pending |
| optimization 1792-1823 | route lazy imports and large player chunk observed | route/player code splitting and CSS consolidation verification | pending |
| budgets 1825-1833 | no approved budget yet | baseline-derived budget document and blocking check | pending |
| PWA cache security 1367-1411 | VitePWA config/source inventory | manifest/worker/cache-exclusion contract | pending |
| dependency security 1836-1879 | npm audit zero advisories | repeated locked audit and sensitive-cache review | pending |

The later performance owner must compare like-for-like mock fixture, viewport, cache, network and browser conditions. A smaller bundle does not override accessibility or media compatibility.

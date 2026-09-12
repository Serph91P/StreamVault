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

## Unmeasured or blocked metrics

Lighthouse, LCP, CLS, TBT, browser request counts, DOM nodes, parsed/transferred payloads, CPU throttling, slow-4G, warm/cold cache, route transition time, realtime update cost, player startup and memory were not collected in this run. Browser baseline initially could not launch due a missing exact Playwright browser revision. Native device performance is not available on this host.

## Performance ledger

| Prompt section/lines | Baseline evidence | Future test/artifact | Status |
| --- | --- | --- | --- |
| measurement 1756-1790 | production build and chunk list | Lighthouse JSON, browser performance entries, bundle report | pending |
| optimization 1792-1823 | route lazy imports and large player chunk observed | route/player code splitting and CSS consolidation verification | pending |
| budgets 1825-1833 | no approved budget yet | baseline-derived budget document and blocking check | pending |
| PWA cache security 1367-1411 | VitePWA config/source inventory | manifest/worker/cache-exclusion contract | pending |
| dependency security 1836-1879 | npm audit zero advisories | repeated locked audit and sensitive-cache review | pending |

The later performance owner must compare like-for-like mock fixture, viewport, cache, network and browser conditions. A smaller bundle does not override accessibility or media compatibility.

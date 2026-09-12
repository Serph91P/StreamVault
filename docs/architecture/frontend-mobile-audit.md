# Mobile and responsive baseline audit

## Required matrix

The Playwright configuration declares every required viewport exactly: small phones 320x568, 360x640, 375x667; modern phones 390x844, 393x873, 412x915, 430x932; landscape 568x320, 667x375, 844x390, 915x412, 932x430; tablets 600x960, 768x1024, 820x1180, 1024x768, 1180x820; desktops 1024x768, 1280x720, 1366x768, 1440x900, 1920x1080.

The P1 baseline test groups the full matrix on Chromium and runs representative phone and desktop assertions in Chromium, Firefox and WebKit. Every listed main mock route receives small phone, modern phone, landscape, tablet and desktop coverage in dark and light themes. This is automation design, not a claim that the matrix has run successfully.

## Observed source baseline

- `useNavigation.ts` has observed shell behavior around 1024 px. Player presentation has existing 768 px behavior. These boundaries are preserved until the one-source responsive migration.
- Raw `100vh`, `transition: all`, hardcoded control dimensions and breakpoint declarations are machine-enumerated in `frontend-inventory.json`.
- `BottomNav.vue`, `AppShell.vue`, player views, streamer/detail/list views, Videos, Settings and onboarding are hotspot paths.
- Existing mock routes and UI standards cover a subset of routes. The baseline browser suite was blocked before browser launch, so no screenshot, DOM geometry, or axe result is represented as collected evidence.

## Rendered audit design

For every visible actionable semantic/native candidate the harness records dimensions, overlap and center-point `document.elementFromPoint()` outcomes. It checks document overflow. It excludes disabled, display-none, hidden, inert, aria-hidden and closed-details content. It does not use force clicks, retries or arbitrary waits. A violation remains a failure unless one exception explicitly names selector, route, reason, owner and expiry/follow-up.

## Mobile ledger

| Requirement | Evidence | Gap and planned proof | Status |
| --- | --- | --- | --- |
| 320 reflow | static existing tests plus new full-matrix design | execute baseline Chromium test and retain JSON/screenshot evidence | pending |
| 44/48 rendered target policy | unit helper detects real violation categories | execute against every route/menu/sheet/player state | pending |
| non-overlap and hit-test | unit GREEN coverage | browser report for fixed navigation, toast, sheets and overlays | pending |
| portrait/landscape | matrix declared | browser and later native device evidence | pending |
| safe areas, keyboard, browser bars | source hotspots identified | real browser/device cases, no simulation claim | pending |
| 200/400 percent reflow | prompt requirement recorded | dedicated zoom/text scale tests | pending |
| touch, coarse/fine pointer | policy recorded | capability-project cases | pending |
| installed PWA | PWA source inventory | installation/standalone setup required | pending |

Native Android/iOS/Windows/macOS proof remains a later manual acceptance gate. Browser emulation must not be relabelled as it.

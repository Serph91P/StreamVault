# Mobile and responsive baseline audit

## Required matrix

The Playwright configuration declares every required viewport exactly: small phones 320x568, 360x640, 375x667; modern phones 390x844, 393x873, 412x915, 430x932; landscape 568x320, 667x375, 844x390, 915x412, 932x430; tablets 600x960, 768x1024, 820x1180, 1024x768, 1180x820; desktops 1024x768, 1280x720, 1366x768, 1440x900, 1920x1080.

The P1 baseline test groups the full matrix on Chromium and runs representative phone and desktop assertions in Chromium, Firefox and WebKit. The complete Chromium route matrix was captured across dark and light themes. Run 210 retained an exact-current-harness report for each of the eight representative Chromium/Firefox states: five completed through axe with focus count 1; Firefox light 390x844 and light 1440x900 each contain one serious-or-critical axe finding; Chromium dark 1440x900 failed at navigation with `Target crashed`; and Firefox dark 390x844 recorded focus count 0. The latter two are stage-classified failed baseline observations, not successful coverage. Run 205 retained four separate nonempty WebKit traces and reports, one for each dark/light 390x844 and 1440x900 state; every report stopped at `readiness` with `locator.count` timing out at 60000 ms before keyboard/tree/axe. They are stage-classified baseline failures, not successful coverage. Browser automation remains distinct from native platform acceptance.

## Observed source baseline

- `useNavigation.ts` has observed shell behavior around 1024 px. Player presentation has existing 768 px behavior. These boundaries are preserved until the one-source responsive migration.
- Raw `100vh`, `transition: all`, hardcoded control dimensions and breakpoint declarations are machine-enumerated in `frontend-inventory.json`.
- `BottomNav.vue`, `AppShell.vue`, player views, streamer/detail/list views, Videos, Settings and onboarding are hotspot paths.
- The full Chromium matrix captured 748 route/viewport observations with screenshots, DOM geometry and overflow metrics. It found 1168 hit-test, 608 overlap and 270 undersized-target baseline defects. Run 210's Chromium/Firefox representative evidence includes two collection/focus failures and two axe-finding states; current WebKit reports all four representative states as bounded readiness failures. These results are retained in the task evidence and are not a mobile acceptance claim.

## Rendered audit design

For every visible actionable semantic/native candidate the harness records dimensions, overlap and center-point `document.elementFromPoint()` outcomes. It checks document overflow. It excludes disabled, display-none, hidden, inert and closed-details content, while retaining visually exposed `aria-hidden` controls as geometry and semantic debt. It does not use force clicks, retries or arbitrary waits. A violation remains a failure unless one exception explicitly names selector, route, reason, owner and expiry/follow-up.

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

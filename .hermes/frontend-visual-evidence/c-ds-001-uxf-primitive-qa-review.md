# C-DS-001 UXF primitive visual QA review

Date: 2026-07-06T13:32:53.622Z
Base URL: http://127.0.0.1:5173
Runner: `node ../../.hermes/frontend-visual-evidence/run-c-ds-001-primitive-qa.mjs`
Mode: `npm run dev:mock -- --host 127.0.0.1 --port 5173`
Result: blocked. Local visual QA ran and refreshed evidence, but the primitive gate cannot be signed off while the capture failure and axe findings remain.

## Theme and viewport matrix

| Theme | Width | Scenarios passed | Horizontal overflow | Axe violation nodes |
| --- | ---: | ---: | --- | ---: |
| dark | 390 | 7/8 | none | 16 |
| dark | 430 | 8/8 | none | 18 |
| dark | 768 | 8/8 | none | 16 |
| dark | 1440 | 8/8 | none | 17 |
| light | 390 | 8/8 | none | 19 |
| light | 430 | 8/8 | none | 21 |
| light | 768 | 8/8 | none | 18 |
| light | 1440 | 8/8 | none | 22 |

## Components and states inspected

| Primitive or product state | Scenario evidence |
| --- | --- |
| tokens | dashboard |
| buttons | dashboard, notification-dialog, streamer-cards, library-cards, library-empty-state, library-delete-modal, settings-notifications-form, settings-proxy-modal |
| cards | dashboard, streamer-cards, library-cards, settings-notifications-form, settings-proxy-modal |
| status badges | dashboard, streamer-cards, library-cards |
| loading states | dashboard |
| sheet or dialog surface | notification-dialog |
| focus states | notification-dialog, library-delete-modal |
| responsive grids | streamer-cards |
| forms | library-cards, library-empty-state, settings-notifications-form, settings-proxy-modal |
| empty state | library-empty-state |
| modal surface | library-delete-modal, settings-proxy-modal |
| disabled states | library-delete-modal, settings-notifications-form |
| tables | settings-notifications-form |
| error states | settings-proxy-modal |

## Issues found

1. Capture failure: `dark/390/settings-notifications-form` timed out waiting for `.settings-view`. This blocks complete dark mobile signoff for forms, tables, disabled button states and cards.
2. Color contrast: axe reports 19 nodes across 11 scenario captures. Representative selectors are `.notification-state .empty-title`, `button[type="submit"] > .btn-content`, `.btn-secondary`, `.btn-danger.btn-action`, `.required`, `#v-2` and `#v-3`.
3. Heading order: axe reports `heading-order` on `h4` in both dark and light `1440/settings-notifications-form` captures.
4. ARIA and landmark noise: axe reports `aria-prohibited-attr` and `region` at 63 nodes each. The sample target is `.panel-entry-btn`, which comes from the `vite-plugin-vue-devtools` overlay configured by `app/frontend/vite.config.ts:4` and `app/frontend/vite.config.ts:11`, so gate runs need that overlay disabled or excluded before axe totals can be treated as release evidence.
5. Scope limits: real backend WebSocket, real HLS playback, real push delivery and native device safe-area behavior were not verified because this ran in Chromium headless with `VITE_USE_MOCK_DATA=true`.

## File references

- Notification empty state contrast path: `app/frontend/src/components/notifications/NotificationState.vue:35` delegates to `EmptyState`; `.empty-title` styling is at `app/frontend/src/components/EmptyState.vue:228`.
- Proxy modal contrast and required-field targets: `app/frontend/src/components/settings/ProxySettingsPanel.vue:265`, `app/frontend/src/components/settings/ProxySettingsPanel.vue:295`, `app/frontend/src/components/settings/ProxySettingsPanel.vue:306`.
- Button content target: `app/frontend/src/components/base/BaseButton.vue:82` with global button variants in `app/frontend/src/styles/main.scss:248` and `app/frontend/src/styles/main.scss:277`.
- Library delete modal targets: `app/frontend/src/views/VideosView.vue:219` and `app/frontend/src/views/VideosView.vue:231`.
- Devtools overlay source: `app/frontend/vite.config.ts:4` and `app/frontend/vite.config.ts:11`.

## UXF-016 and UXF-017 source evidence

- UXF-016 requires status, content, settings, danger, diagnostics and media panel variants in the design system: `.hermes/streamvault-screenshot-ux-findings.md:29`.
- UXF-017 requires Nielsen, JTBD, task flows and responsive QA as acceptance gates: `.hermes/streamvault-screenshot-ux-findings.md:30`.
- Product plan requires explicit empty, loading and error states before page implementation proceeds: `docs/frontend-overhaul-product-ux-plan.md:104` to `docs/frontend-overhaul-product-ux-plan.md:113`.
- Primitive README documents canonical status badges, empty/loading/error primitives, form QA and visual QA expectations: `app/frontend/src/components/base/README.md:15`, `app/frontend/src/components/base/README.md:16`, `app/frontend/src/components/base/README.md:41`, `app/frontend/src/components/base/README.md:79` to `app/frontend/src/components/base/README.md:102`.
- Feature parity map keeps downstream product routes blocked for full UXF-017 route QA: `.hermes/streamvault-feature-parity-map.md:27` to `.hermes/streamvault-feature-parity-map.md:55`.

## Verification commands

- `node ../../.hermes/frontend-visual-evidence/run-c-ds-001-primitive-qa.mjs` returned `blocked: true`, 63 screenshots and the axe summary above.
- `npm run lint:tokens` returned `design-token lint: no violations`.
- `git diff --check` returned exit code 0 with no output.

## Evidence files

- Matrix: `.hermes/frontend-visual-evidence/c-ds-001-primitive-qa-matrix.md`
- Raw JSON: `.hermes/frontend-visual-evidence/c-ds-001-primitive-qa-results.json`
- Runner script: `.hermes/frontend-visual-evidence/run-c-ds-001-primitive-qa.mjs`
- This review: `.hermes/frontend-visual-evidence/c-ds-001-uxf-primitive-qa-review.md`
- Screenshots captured in latest run: 63

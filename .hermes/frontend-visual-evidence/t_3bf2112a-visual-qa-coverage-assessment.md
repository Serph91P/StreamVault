# t_3bf2112a visual QA coverage assessment

Date: 2026-07-06T14:53:51.407Z
Task: Assess visual QA coverage across themes and breakpoints for C-DS-001.
Workspace: /opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final

## Local method

- Started the mock frontend with `npm run dev:mock -- --host 127.0.0.1 --port 5173` through `with_server.py`.
- Re-ran `node ../../.hermes/frontend-visual-evidence/run-c-ds-001-primitive-qa.mjs` from `app/frontend`.
- The runner forced `localStorage.streamvault-theme` to `dark` and `light`, then captured Chromium headless screenshots at 390, 430, 768 and 1440 px.
- Re-read the refreshed matrix and source references after the run.
- Ran `git diff --check -- .hermes/frontend-visual-evidence app/frontend/src/components/base/README.md` and `cd app/frontend && npm run lint:tokens`.

## Theme and viewport coverage matrix

| Theme | Width | Scenarios passed | Horizontal overflow | Axe violation nodes | Result |
| --- | ---: | ---: | --- | ---: | --- |
| dark | 390 | 8/8 | none | 18 | covered, blocked by axe |
| dark | 430 | 8/8 | none | 18 | covered, blocked by axe |
| dark | 768 | 8/8 | none | 17 | covered, blocked by axe |
| dark | 1440 | 8/8 | none | 18 | covered, blocked by axe |
| light | 390 | 8/8 | none | 20 | covered, blocked by axe |
| light | 430 | 8/8 | none | 20 | covered, blocked by axe |
| light | 768 | 8/8 | none | 19 | covered, blocked by axe |
| light | 1440 | 8/8 | none | 20 | covered, blocked by axe |

Scenarios per theme-width: dashboard, notification-dialog, streamer-cards, library-cards, library-empty-state, library-delete-modal, settings-notifications-form, settings-proxy-modal.

Evidence files:

- `.hermes/frontend-visual-evidence/c-ds-001-primitive-qa-matrix.md`
- `.hermes/frontend-visual-evidence/c-ds-001-primitive-qa-results.json`
- `.hermes/frontend-visual-evidence/run-c-ds-001-primitive-qa.mjs`
- 64 screenshots under `.hermes/frontend-visual-evidence/`, named by theme, width and scenario.

## Component and state coverage

| Area | Covered by scenarios | Source or contract reference |
| --- | --- | --- |
| Tokens | dashboard | `app/frontend/src/components/base/README.md:51` to `app/frontend/src/components/base/README.md:59` |
| Status badges | dashboard, streamer-cards, library-cards | `app/frontend/src/components/base/README.md:15` |
| Buttons | all eight scenarios | `app/frontend/src/components/base/README.md:7`, `app/frontend/src/components/base/README.md:45` |
| Cards | dashboard, streamer-cards, library-cards, settings-notifications-form, settings-proxy-modal | `app/frontend/src/components/base/README.md:21` to `app/frontend/src/components/base/README.md:25` |
| Forms | library-cards, library-empty-state, settings-notifications-form, settings-proxy-modal | `app/frontend/src/components/base/README.md:93` to `app/frontend/src/components/base/README.md:102` |
| Sheets and dialogs | notification-dialog, library-delete-modal, settings-proxy-modal | `app/frontend/src/components/base/README.md:61` to `app/frontend/src/components/base/README.md:67` |
| Empty states | notification-dialog, library-empty-state | `app/frontend/src/components/base/README.md:16`, `app/frontend/src/components/base/README.md:36` to `app/frontend/src/components/base/README.md:42` |
| Error states | notification-dialog, settings-proxy-modal | `app/frontend/src/components/base/README.md:16`, `app/frontend/src/components/base/README.md:18`, `app/frontend/src/components/base/README.md:19` |
| Loading states | dashboard | `app/frontend/src/components/base/README.md:17` |
| Disabled states | library-delete-modal, settings-notifications-form | `app/frontend/src/components/base/README.md:45` |
| Focus states | notification-dialog, library-delete-modal | `app/frontend/src/components/base/README.md:87` |
| Tables | settings-notifications-form | `app/frontend/src/components/settings/NotificationSettingsPanel.vue:87` to `app/frontend/src/components/settings/NotificationSettingsPanel.vue:100` |

## UXF-016 and UXF-017 representation

- UXF-016 asks C-DS-001 to define status, content, settings, danger, diagnostics and media panel variants. Source: `.hermes/streamvault-screenshot-ux-findings.md:29`.
- UXF-017 asks Nielsen, JTBD, task flows and responsive QA to act as acceptance gates for each core route. Source: `.hermes/streamvault-screenshot-ux-findings.md:30`.
- The product UX plan requires each page to have explicit empty, loading and error states before implementation begins. Source: `docs/frontend-overhaul-product-ux-plan.md:104` to `docs/frontend-overhaul-product-ux-plan.md:113`.
- This C-DS-001 primitive pass represents status, content, settings and danger surfaces through dashboard, streamer cards, library cards, settings forms and delete/proxy modals.
- Diagnostics and media product states remain only partially represented at the primitive level. The stricter route parity map keeps Admin Diagnostics, stored player, live player, Queue, Notification Center, PWA and other product routes blocked until route-specific visual QA exists. Source: `.hermes/streamvault-feature-parity-map.md:27` to `.hermes/streamvault-feature-parity-map.md:53`.

## WCAG, contrast and layout risks

1. Blocking WCAG contrast findings remain. Current axe summary: `color-contrast=20` nodes in 15 scenario captures.
2. Dialog and sheet captures still report `aria-prohibited-attr=64` and `region=64`. The earlier source review ties at least some targets to the Vite devtools overlay, but this run still cannot be used as clean release evidence until the overlay is disabled or excluded.
3. Heading order remains `heading-order=2` in settings notification form captures.
4. Light 430 proxy modal examples have a known long URL clipping risk. Source: `app/frontend/src/components/settings/ProxySettingsPanel.vue:264` to `app/frontend/src/components/settings/ProxySettingsPanel.vue:320`.
5. Dark 768 notification settings form has a known bottom nav overlap risk around the save action. Sources: `app/frontend/src/components/settings/NotificationSettingsPanel.vue:74` to `app/frontend/src/components/settings/NotificationSettingsPanel.vue:85` and `app/frontend/src/components/navigation/BottomNav.vue:49` to `app/frontend/src/components/navigation/BottomNav.vue:77`.
6. Native safe-area behavior, real backend WebSocket, real HLS playback and real push delivery were not verified. The current run used headless Chromium and `VITE_USE_MOCK_DATA=true`.

## Verification output

- `node ../../.hermes/frontend-visual-evidence/run-c-ds-001-primitive-qa.mjs` returned `blocked=true`, `screenshots=64`, `aria-prohibited-attr=64`, `region=64`, `color-contrast=20`, `heading-order=2`.
- `git diff --check -- .hermes/frontend-visual-evidence app/frontend/src/components/base/README.md` returned exit code 0 with no output.
- `cd app/frontend && npm run lint:tokens` returned `design-token lint: no violations`.

## Decision

Local visual QA coverage is present for dark and light themes at 390, 430, 768 and 1440 px, with all 64 scenario captures produced. The C-DS-001 design-system gate remains review-required because the visual QA run is blocked by accessibility findings, known responsive layout risks and unverified real product integrations.

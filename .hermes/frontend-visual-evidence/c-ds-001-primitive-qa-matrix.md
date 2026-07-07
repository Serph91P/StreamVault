# C-DS-001 primitive visual QA matrix

Date: 2026-07-06T16:21:30.006Z
Base URL: http://127.0.0.1:4174
QA run label: C-DS-001G final production preview after whitespace fix
Scope: dark, light themes at 390, 430, 768, 1440 px.

## Result

Passed. Local visual QA completed without blocking regressions.

## Theme and breakpoint coverage

| Theme | Width | Scenarios passed | Horizontal overflow | App axe nodes | Overlay axe nodes |
| --- | ---: | ---: | --- | ---: | ---: |
| dark | 390 | 8/8 | none | 0 | 0 |
| dark | 430 | 8/8 | none | 0 | 0 |
| dark | 768 | 8/8 | none | 0 | 0 |
| dark | 1440 | 8/8 | none | 0 | 0 |
| light | 390 | 8/8 | none | 0 | 0 |
| light | 430 | 8/8 | none | 0 | 0 |
| light | 768 | 8/8 | none | 0 | 0 |
| light | 1440 | 8/8 | none | 0 | 0 |

## Primitive coverage

| Primitive area | Scenario evidence |
| --- | --- |
| tokens | dashboard |
| buttons | dashboard, notification-dialog, streamer-cards, library-cards, library-empty-state, library-delete-modal, settings-notifications-form, settings-proxy-modal |
| cards | dashboard, streamer-cards, library-cards, settings-notifications-form, settings-proxy-modal |
| status badges | dashboard, streamer-cards, library-cards |
| loading states | dashboard |
| sheet/dialog surface | notification-dialog |
| empty/error/loading states | notification-dialog |
| focus states | notification-dialog, library-delete-modal |
| responsive grids | streamer-cards |
| forms | library-cards, library-empty-state, settings-notifications-form, settings-proxy-modal |
| empty state | library-empty-state |
| modal surface | library-delete-modal, settings-proxy-modal |
| disabled states | library-delete-modal, settings-notifications-form |
| tables | settings-notifications-form |
| error states | settings-proxy-modal |

## Observed regressions and WCAG concerns

- No blocking visual regressions were detected by the automated matrix.

## Axe summary

### App DOM

| Rule | Nodes |
| --- | ---: |
| none | 0 |

### Devtools overlay DOM

| Rule | Nodes |
| --- | ---: |
| none | 0 |

## Devtools overlay isolation

- Overlay selectors excluded from app classification: .panel-entry-btn
- Captures with .panel-entry-btn in the DOM: 0/64
- App axe nodes after overlay target classification: 0
- Overlay axe nodes: 0
- Verdict: aria-prohibited-attr and region are not app DOM issues in this production preview run; .panel-entry-btn is absent, so prior .panel-entry-btn counts are devtools overlay noise.
- Command output artifact: .hermes/frontend-visual-evidence/c-ds-001p-command-output.txt

## Unverified coverage

- Real backend WebSocket, real HLS playback and real push delivery were not verified because this matrix ran against VITE_USE_MOCK_DATA=true.
- Manual visual judgment beyond captured screenshots remains a human review step. The script flags overflow, focus movement and axe results, but does not replace final design review.
- Native device safe-area behavior was not verified. Coverage used Chromium headless viewport widths only.

## Evidence files

- Raw JSON: `.hermes/frontend-visual-evidence/c-ds-001-primitive-qa-results.json`
- QA script: `.hermes/frontend-visual-evidence/run-c-ds-001-primitive-qa.mjs`
- Screenshots captured: 64

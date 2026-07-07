# D-SHELL-001 visual QA report

Date: 2026-07-06
Route: `/`
Preview: production build served with `VITE_USE_MOCK_DATA=true npm run build-only` and `npm run preview -- --host 127.0.0.1 --port 4173`

## Result

Pass. The shell density and utility model have no visual QA blockers in the sampled viewports.

## Viewports

- 390 x 844: mobile shell, bottom nav visible, no horizontal overflow, all sampled targets at least 44 px.
- 768 x 1024: tablet shell, bottom nav visible, no horizontal overflow, all sampled targets at least 44 px.
- 1024 x 768: desktop shell, sidebar visible, no horizontal overflow, all sampled targets at least 44 px.
- 1280 x 720: desktop shell, sidebar visible, no horizontal overflow, all sampled targets at least 44 px.
- 1440 x 900: desktop shell, sidebar visible, no horizontal overflow, all sampled targets at least 44 px.

## Evidence files

- `.hermes/frontend-visual-evidence/d-shell-001/metrics.json`
- `.hermes/frontend-visual-evidence/d-shell-001/mobile-390-dashboard.png`
- `.hermes/frontend-visual-evidence/d-shell-001/tablet-768-dashboard.png`
- `.hermes/frontend-visual-evidence/d-shell-001/desktop-1024-dashboard.png`
- `.hermes/frontend-visual-evidence/d-shell-001/desktop-1024-notifications.png`
- `.hermes/frontend-visual-evidence/d-shell-001/desktop-1024-queue.png`
- `.hermes/frontend-visual-evidence/d-shell-001/desktop-1280-dashboard.png`
- `.hermes/frontend-visual-evidence/d-shell-001/desktop-1280-notifications.png`
- `.hermes/frontend-visual-evidence/d-shell-001/desktop-1280-queue.png`
- `.hermes/frontend-visual-evidence/d-shell-001/desktop-1440-dashboard.png`
- `.hermes/frontend-visual-evidence/d-shell-001/desktop-1440-notifications.png`
- `.hermes/frontend-visual-evidence/d-shell-001/desktop-1440-queue.png`

## Automated metrics

`node .hermes/frontend-visual-evidence/d-shell-visual-check.cjs` returned:

```json
{
  "viewports": 5,
  "blocked": false,
  "blockers": []
}
```

Key sampled metrics from `metrics.json`:

- Header height: 56 px in all sampled viewports.
- Mobile bottom nav: 68 px high with main content bottom padding of 68 px.
- Desktop sidebar: 232 px wide, main content starts at 248 px.
- 390 px mobile targets: header utilities are 44 x 44 px, bottom nav tabs are 68 x 52 px.
- 1024 px desktop targets: header utilities are at least 44 px high, sidebar rows are 52 px high, sidebar toggle is 44 px high.

## UXF-002 notes

- Desktop chrome is denser: header moved from the inherited 70 px layout to a 56 px fixed shell header.
- Sidebar is lighter: expanded width is 232 px and collapsed width is 72 px, with 44 px minimum rows.
- Utilities are grouped as one global cluster: Jobs, Alerts, theme and logout share a 44 px target model.
- Mobile keeps five bottom nav destinations, reserves bottom safe spacing and keeps each tab above the 44 px Fitts target.

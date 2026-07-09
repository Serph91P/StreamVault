# Mobile PWA QA results

Task: t_d8d76c49
Branch: feat/frontend-product-overhaul-final
Workspace: /opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final
Date: 2026-07-07

## Automated checks

Run from app/frontend unless noted.

1. `npm run type-check`
   - Result: pass.

2. `npm run lint:tokens`
   - Result: pass.
   - Output: `design-token lint: no violations`.

3. `npx eslint .`
   - Result: pass with warnings.
   - Output summary: 0 errors, 166 warnings.
   - Warning class: existing `@typescript-eslint/no-explicit-any` warnings across the app.

4. `npm run build`
   - Result: pass.
   - Output summary: Vite build completed, PWA generated `dist/sw.js` and `dist/workbox-dcde9eb3.js`.
   - Non-blocking build warnings: Rolldown `INVALID_ANNOTATION` warnings from `node_modules/@vueuse/core`, `INEFFECTIVE_DYNAMIC_IMPORT` for `useWebSocket`, and stale Browserslist data.

5. `VITE_USE_MOCK_DATA=true npm run build`
   - Result: pass.
   - Purpose: production PWA bundle with mock auth and data for mobile route QA.
   - Output summary: Vite build completed, PWA generated `dist/sw.js` and `dist/workbox-dcde9eb3.js`.

6. `git diff --check -- .`
   - Result: pass.

7. `grep -rP "[\x{2013}\x{2014}]" -- src/components/AppShell.vue src/components/PWAInstallPrompt.vue src/components/navigation/BottomNav.vue src/components/settings/PWAPanel.vue src/composables/usePWA.ts vite.config.ts && exit 1 || true`
   - Result: pass, no forbidden en or em dashes found in scoped PWA/mobile files.

## Manual and emulated QA

Server:

- Command: `npm run preview -- --host 127.0.0.1 --port 4173`
- URL: `http://127.0.0.1:4173`
- Bundle: `VITE_USE_MOCK_DATA=true npm run build`

Device and browser:

- Playwright Chromium, headless.
- Device profile: Pixel 7 emulation.
- Viewport: mobile profile from Playwright device descriptor.
- Service workers: allowed.
- Evidence script: `.hermes/mobile-pwa-qa.cjs`.
- Screenshots:
  - `.hermes/frontend-visual-evidence/mobile-pwa-qa/settings-pwa-mobile.png`
  - `.hermes/frontend-visual-evidence/mobile-pwa-qa/bottom-nav-routes.png`
  - `.hermes/frontend-visual-evidence/mobile-pwa-qa/offline-mobile.png`

Executed command:

`node .hermes/mobile-pwa-qa.cjs`

Result: pass, 7 of 7 checks passed.

Checks performed:

1. PWA settings route access
   - Result: pass.
   - `/settings?section=pwa` opened on mobile without login redirect.
   - Verified visible PWA and Mobile heading.

2. No blind notification permission prompt
   - Result: pass.
   - Instrumented `Notification.requestPermission` call count.
   - Page load count stayed at `0` before any user action.

3. Push permission priming
   - Result: pass.
   - First click on `Review first` only revealed primer details.
   - Permission call count stayed at `0` during primer review.
   - Clicking `Allow notifications` caused exactly one explicit permission request.

4. Bottom navigation and target route access
   - Result: pass.
   - Bottom navigation was visible with runtime height `68px`.
   - Reached Dashboard, Streamers, Library, Subscriptions, and Settings tabs without auth redirects.

5. Offline and reconnect UI
   - Result: pass.
   - Browser offline mode triggered visible offline copy.
   - Online event recovered without page crash.
   - Screenshot captured as `offline-mobile.png`.

6. Safe-area and fixed bottom layout
   - Result: pass.
   - Runtime bottom nav style: `position=fixed`, `bottom=0px`, `height=68px`, `paddingBottom=6px`, `zIndex=1000`.
   - Source inspection also confirmed `env(safe-area-inset-bottom, 0px)` usage in BottomNav and PWAInstallPrompt.

7. Guided install prompt behavior
   - Result: pass.
   - Synthetic `beforeinstallprompt` event showed the custom install prompt.
   - The app did not show the custom prompt before installability was signaled.
   - `Setup guide` navigated to `/settings?section=pwa`.

## Service worker and PWA notes

- Service worker registration succeeded in the preview run.
- Runtime check returned one service worker registration scoped to `http://127.0.0.1:4173/`.
- Native browser install UI cannot be completed in this headless Chromium environment, so install prompt QA was limited to the app-level guided prompt and route behavior.

## Remaining observations

- The Subscriptions tab logged a console error while using the generic QA API stub: `Failed to load streamers: Cannot read properties of undefined (reading 'length')`. The tab route still opened and did not redirect to login. This appears to be a QA stub shape mismatch, not a PWA/mobile regression.
- The preview server has no backend WebSocket endpoint, so a WebSocket handshake error is expected in this isolated frontend QA run.

# StreamVault PWA and mobile pass

Date: 2026-07-05
Task: KAN2-007
Branch: feat/frontend-overhaul-v2

## Service worker ownership

VitePWA and Workbox own the single generated service worker through `virtual:pwa-register` in `app/frontend/src/main.ts`.

Custom push and notification click handlers remain in `app/frontend/public/push-sw.js`. The generated Workbox service worker imports them through `workbox.importScripts: ['push-sw.js']` in `app/frontend/vite.config.js`, so push remains functional without a second registered worker.

Removed stale generated public artifact `app/frontend/public/workbox-74f2ef77.js`. Generated Workbox output now belongs in `app/frontend/dist` after `npm run build-only`.

## PWA install UX

- `PWAInstallPrompt.vue` still waits for the browser `beforeinstallprompt` event and never triggers install without a user button.
- The prompt appears after a short delay only when installable, not installed and not dismissed.
- Dismissal is stored for seven days through existing app storage.
- The previous 10 s polling interval was removed. The component now watches installability and clears timers on unmount.
- The mobile card clears the safe area with `env(safe-area-inset-bottom)` and keeps action buttons full width below `md`.
- Desktop keeps a constrained floating card with `max-width: 400px` so install does not dominate the shell.

## Push permission UX

- `PWAPanel.vue` keeps the permission request button driven through `Enable Notifications`.
- The permission copy explains value before requesting browser permission.
- Denied permission shows troubleshooting guidance.
- Status feedback now uses `role="status"`.
- Mobile setting actions become full width below `md` for easier touch use.

## Mobile shell safety

- `AppShell.vue` now owns the authenticated header, notification panel and navigation wrapper separately from `App.vue`.
- `App.vue` is thinner and keeps the router view, toast container, PWA prompt and realtime wiring.
- `NavigationWrapper.vue` continues to reserve bottom nav safe area space for main content.
- `BottomNav.vue` already enforces 44 px minimum tab targets and safe area padding.

## Changed files

| File | Change |
| --- | --- |
| `app/frontend/public/workbox-74f2ef77.js` | Deleted stale generated Workbox artifact |
| `app/frontend/vite.config.js` and `app/frontend/vite.config.ts` | Import `push-sw.js` into the generated Workbox service worker |
| `app/frontend/src/main.ts` | Exposes VitePWA registration, refresh, offline and error callbacks as custom browser events |
| `app/frontend/src/App.vue` | Moves shell header and notification panel rendering into `AppShell` |
| `app/frontend/src/components/AppShell.vue` | New authenticated shell boundary for header, notifications and navigation |
| `app/frontend/src/components/PWAInstallPrompt.vue` | Removes interval polling, adds timer cleanup, improves safe-area handling |
| `app/frontend/src/components/settings/PWAPanel.vue` | Adds accessible status feedback and mobile full-width actions |
| `.hermes/streamvault-pwa-mobile-pass.md` | Documents this pass and verification contract |

## Verification contract

Run from `app/frontend`:

```sh
npm run type-check
npm run build-only
```

Expected build artifacts:

- `dist/sw.js` exists.
- `dist/sw.js` contains `importScripts("push-sw.js")`.
- `dist/push-sw.js` exists.

Source checks:

```sh
rg -n "registerSW|serviceWorker\.register|/sw\.js" app/frontend/src app/frontend/public
rg -n "workbox" app/frontend/public
rg '[\u2013\u2014]' app/frontend/vite.config.js app/frontend/src/main.ts app/frontend/src/App.vue app/frontend/src/components/AppShell.vue app/frontend/src/components/PWAInstallPrompt.vue app/frontend/src/components/settings/PWAPanel.vue .hermes/streamvault-pwa-mobile-pass.md
git diff --check
```

Expected source check result:

- `registerSW` appears only in `app/frontend/src/main.ts`.
- No manual `serviceWorker.register` call appears.
- No source uses `/sw.js` directly.
- No generated `workbox-*` file remains in `app/frontend/public`.
- No em dash or en dash characters appear in changed text files.
- `git diff --check` is clean.

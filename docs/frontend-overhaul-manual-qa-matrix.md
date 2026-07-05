# Frontend Overhaul Manual QA Matrix

Date: 2026-07-05
Kanban task: KAN-026
Branch: feat/frontend-overhaul-plan
Frontend path: app/frontend

## Scope

This matrix covers desktop, mobile, PWA, push and realtime checks available in the local QA environment. Device-only checks are recorded as Not available when this environment cannot provide the required OS, browser, installed PWA or push provider.

## Environment

- Repo: `/opt/data/workspace/github_repos/StreamVault-frontend-overhaul`
- App mode used for browser checks: `npm run dev:mock -- --host 127.0.0.1 --port 5174`
- Browser URL: `http://127.0.0.1:5174/`
- Backend service: not started for this QA pass
- Mobile hardware: not available in this environment
- iOS and Android installed PWA: not available in this environment

## Automated and local checks

| Check | Status | Evidence | Notes |
| --- | --- | --- | --- |
| Design token lint | Pass | `npm run lint:tokens` printed `design-token lint: no violations` | Command run in `app/frontend`. |
| Type check | Pass | `npm run type-check` completed with exit code 0 | `vue-tsc --build`. |
| Production build | Pass | `npm run build-only` completed with exit code 0 and generated `dist/sw.js`, `dist/workbox-dcde9eb3.js` | Build warnings are from Rolldown pure annotations, static plus dynamic WebSocket import, and stale Browserslist data. |
| Diff whitespace check | Pass | `git diff --check` completed with exit code 0 | Run after build in `app/frontend`. |
| PWA manifest served by Vite dev server | Pass | `curl http://127.0.0.1:5174/manifest.webmanifest` returned JSON with `display: standalone`, `start_url: /?source=pwa`, `scope: /`, maskable icons and portrait orientation | Confirms local asset availability. |
| Service worker asset served by Vite dev server | Pass | `curl -I http://127.0.0.1:5174/sw.js` returned HTTP 200 and `Content-Type: text/javascript` | Dev server can serve the worker file. |
| Generated worker custom push import | Pass | `dist/sw.js` does not contain `importScripts('/pwa/push-sw.js')`; `app/main.py` contains the backend injection route for `/sw.js` | Pass for backend-served production path. Static Vite preview alone still depends on backend injection not being bypassed. |

## Manual browser matrix

| Area | Scenario | Status | Evidence | Notes |
| --- | --- | --- | --- | --- |
| Desktop app shell | Load dashboard in mock mode | Pass | Browser showed `Dashboard`, sidebar with Dashboard, Streamers, Library, Subscriptions, Settings, header Jobs, Notifications, theme and Logout | No console messages or JS errors after load. |
| Desktop dashboard | Operational overview content | Pass | Browser showed realtime offline badge, live count 2, recording count 1, queue paused, failures 0 and latest videos list | Mock data rendered without backend. |
| Desktop streamers | Navigate to Streamers | Pass | Browser showed `Streamers`, search box, All 4, Live 2, Recording 1, Offline 2 and streamer cards | No console messages or JS errors after navigation. |
| Desktop library | Navigate to Library | Pass | Browser showed `Videos`, search, Filters, sort dropdown and 12 video cards | No console messages or JS errors after navigation. |
| Desktop notification center | Open header notification button | Pass | Browser opened a dialog with `Notifications`, `All caught up` and empty-state copy | Confirms product notification surface renders. |
| Desktop queue surface | Dashboard queue panel | Pass | Browser showed Queue panel with Paused, Active 0, Pending 0, Failed 0, Workers 0 and Refresh queue fallback | Header Jobs button did not open a separate visible panel in this viewport during the quick pass, but the dashboard queue surface is available. |
| Desktop settings PWA panel | Navigate Settings then PWA & Mobile | Pass | Browser showed Installation Status, Connection Status Online, Browser Support Supported, Notification Permission Denied, Push Subscription Not Subscribed, Offline Support Enabled and Background Sync Enabled | Permission state belongs to the test browser. |
| Desktop theme toggle | Header theme button exists and is keyboard/button accessible | Pass | Browser exposed button `Switch to dark mode` | Visual color comparison was not captured as a separate screenshot. |
| Mobile primary navigation | Bottom nav presence in DOM | Pass | Accessibility snapshot included nav buttons Dashboard, Streamers, Library, Subscriptions and Settings | Actual mobile viewport was not available through this browser session. |
| Mobile viewport layout | Touch layout on real narrow viewport | Not available | No mobile browser or viewport emulation tool was available in this session | Needs follow-up on real device or browser automation with viewport control. |
| Mobile PWA settings | PWA & Mobile content on real narrow viewport | Not available | No mobile browser or viewport emulation tool was available in this session | Content rendered on desktop. Real mobile wrapping and sticky behavior still need device validation. |
| Mobile safe area | Installed PWA safe-area handling | Not available | No installed mobile PWA environment was available | Needs Android and iOS device checks. |
| Keyboard smoke | Primary routes and panels exposed as buttons or links in accessibility tree | Pass | Browser accessibility tree showed links, buttons and dialog role for notification panel | Full keyboard tab-order audit was not executed. |

## Push and PWA matrix

| Area | Scenario | Status | Evidence | Notes |
| --- | --- | --- | --- | --- |
| PWA install metadata | Manifest contains installable metadata | Pass | Manifest has name, short_name, start_url, display standalone, scope, background color, theme color and icons | Install prompt itself depends on browser heuristics and was not forced. |
| Service worker registration source | Single frontend registration owner | Pass | Source read verified `src/main.ts` uses `virtual:pwa-register`; `usePWA.ts` resolves the existing registration for push subscription state and no longer registers `/sw.js`; `index.html` no longer loads `/registerSW.js` | `/registerSW.js` remains as a backend no-op compatibility response for stale cached pages. |
| Push support UI | Browser support and permission state visible | Pass | PWA & Mobile panel showed Browser Support Supported and Notification Permission Denied | This confirms status rendering, not successful subscription. |
| Push permission denied UI | Denied permission guidance | Pass | Panel showed troubleshooting copy instructing the user to update browser site permissions | Permission state came from the test browser. |
| Push subscription success | Subscribe through `/api/push/subscribe` | Blocked | Backend service was not started and notification permission was denied in the browser | Requires backend, VAPID key and granted notification permission. |
| Push test send | Server push test from UI | Blocked | UI only shows Send Test after permission granted and subscription exists | Requires a real subscription. |
| Local notification test | Local browser notification from PWA panel | Blocked | UI hides the local test button unless permission is granted and subscribed | Requires browser notification permission. |
| notificationclick target normalization | Source behavior | Pass | `public/push-sw.js` reads `target_url`, `internal_url` or `url`, normalizes `/streamer/:id` to `/streamers/:id`, focuses existing clients or opens a target window | Source verified, not device clicked. |
| Android Chrome installed PWA | Receive and click Web Push | Not available | No Android device or installed PWA environment was available | Required by product plan. |
| Android Chrome browser tab | Receive and click Web Push in browser tab | Not available | No Android browser environment was available | Required by product plan. |
| iOS or iPadOS Home Screen app | Receive and click Web Push | Not available | No iOS or iPadOS device with Home Screen installation was available | Required by product plan. |
| Unsupported iOS browser tab | Confirm no Web Push in normal iOS browser tab | Not available | No iOS or iPadOS browser environment was available | Required by product plan. |

## Realtime matrix

| Area | Scenario | Status | Evidence | Notes |
| --- | --- | --- | --- | --- |
| Realtime dashboard state | App shows disconnected or offline state without backend | Pass | Dashboard showed `REALTIME OFFLINE` while mock data still rendered | Acceptable for local mock run without backend. |
| Realtime store source | Central store exists and exposes connection state | Pass | Source read verified `src/stores/realtime.ts` wraps `WebSocketManager`, exposes `connectionStatus`, `recentEvents`, online state and typed event handlers | Source-level verification. |
| Notification store source | Notification persistence and read state exist | Pass | Source read verified `src/stores/notifications.ts` supports load, sync, add, mark read, mark unread, remove and clear | Source-level verification. |
| Live WebSocket connection | Connect to backend `/ws` | Blocked | Backend service was not started for this QA pass | Needs integrated backend run. |
| Reconnect after server interruption | Drop and restore backend WebSocket | Blocked | Backend service was not started for this QA pass | Needs integrated backend run. |
| Event replay after missed connection | Replay missed events by cursor | Not available | Product plan documents backend gap: no durable event ids or replay API in current backend | Cannot pass until backend replay support exists. |
| Queue realtime updates | Receive queue stats over WebSocket | Blocked | Backend service was not started for this QA pass | Dashboard fallback queue UI rendered. |
| Notification realtime ingestion | Receive WebSocket event and add notification | Blocked | Backend service was not started for this QA pass | Store source exists, live event delivery not exercised. |

## Findings and risks

1. No blocking frontend build or type issues were found in this QA pass.
2. Device-only push checks remain unverified and must be run on Android Chrome, Android installed PWA, iOS or iPadOS Home Screen app, and unsupported iOS browser tab.
3. The production backend route injects `/pwa/push-sw.js` into `/sw.js`, while the raw generated `dist/sw.js` does not contain that import. QA should avoid validating push behavior from a static frontend-only preview as if it were the backend-served production path.
4. Realtime live behavior could not be fully exercised without a running backend WebSocket server.
5. Event replay remains not available because the current backend does not expose durable event ids or a replay cursor API.

## Required follow-up before release

| Follow-up | Owner | Reason |
| --- | --- | --- |
| Run Android Chrome installed PWA push receive and click test | Manual device QA | Required platform behavior cannot be emulated here. |
| Run Android Chrome browser tab push receive and click test | Manual device QA | Required platform behavior cannot be emulated here. |
| Run iOS or iPadOS Home Screen push receive and click test | Manual device QA | iOS Web Push has platform-specific install requirements. |
| Run unsupported iOS browser tab negative check | Manual device QA | Confirms documented limitation. |
| Run backend-integrated realtime smoke | QA with backend | Needed for `/ws`, queue updates and notification ingestion. |

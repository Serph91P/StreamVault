# StreamVault UX audit

Date: 2026-07-05
Branch: feat/frontend-overhaul-v2
Head: 8766fe23

## Scope

This is a fresh phase 1 audit against current `develop` after the previous frontend overhaul landed. It does not assume that the prior overhaul satisfies the new prompt. It uses Graphify output, current source inventory and the historical docs as context only.

The follow-up KAN2-002 concept is now captured in `.hermes/streamvault-ux-ia-concept.md`. Downstream implementation tasks must treat that file as the IA contract for navigation, Jobs to be Done, journeys, task flows, accessibility and perceived performance.

## Jobs to be Done

| Job | Current support | Gap to close |
| --- | --- | --- |
| Monitor streamers | Dashboard and Streamers exist with realtime support | Verify the top status is understandable in 3 seconds with real data and browser QA |
| Know who is live | Streamers, Dashboard and live player can show live state | Need stronger status language and consistent live/recording badges across all cards |
| Understand recording state | Active recordings exist in composables and dashboard areas | Recording state should become a first class store and component model |
| Start or follow recording | Force recording and settings flows exist | Actions must be contextual, safe and clear on mobile |
| Find and play videos | Library and player routes exist | Video browsing still lives in a large view and needs stronger media app polish |
| Understand notifications | Notification store and center exist | Cross channel WebSocket, Push and Apprise language needs clearer UI separation |
| Install PWA and enable Push | PWAPanel and VitePWA path exist | Requires real device QA and a more guided permission journey |
| Change settings safely | Settings panels exist | SettingsView remains a 1,354 line page and needs stronger information architecture |
| Inspect system or queue | Admin and queue monitors exist | Diagnostics must stay separated from product status |

## Nielsen heuristic evaluation

| Heuristic | Finding | Required next action |
| --- | --- | --- |
| Visibility of system status | Dashboard, realtime and notification stores exist, but large pages still distribute status rendering | Make Dashboard, Queue and Notification status use one status grammar |
| Match to user expectations | Navigation labels improved, but technical debug concepts still appear in diagnostics and settings code paths | Keep admin language out of user settings and product flows |
| User control and exits | Sheets and panels exist, but mobile deep routes need browser validation | Verify escape, close, back and cancel behavior on mobile sizes |
| Consistency and standards | Shared primitives exist, but many large views still carry local classes and button patterns | Enforce component rules before page rebuilds |
| Error prevention | Push permission flow improved | Add clearer confirmation and recovery for risky recording/settings actions |
| Recognition over recall | Status badges and filters exist | Ensure every status has text and consistent icon plus label |
| Efficiency | Lazy routes and global actions exist | Add fast filters and quick actions without making the UI noisy |
| Minimalism | Debug UI was reduced | Recheck Admin, Settings and PWA surfaces for leftover test affordances |
| Error diagnosis | PlayerError and notification states exist | Use readable recovery copy for HLS, recording and push failures |
| Help in context | PWA copy exists | Add inline explanations for advanced settings and diagnostics links |

## User journeys

### New user setup

1. User is routed to setup or onboarding.
2. User should see a focused, branded flow, not the app shell.
3. PWA push should not be requested before explanation.
4. Success should land on Dashboard with a clear next action.

### Dashboard status check

1. User opens `/`.
2. Within 3 seconds they should know live count, recording count, queue state and critical failures.
3. The main action should be obvious: open live, inspect recording, add streamer or review notification.
4. Reconnect state must be visible but not alarming when normal.

### Add streamer

1. User starts at Streamers.
2. Add Streamer must make manual vs import obvious.
3. Validation errors stay near fields.
4. Success returns to a streamer status context.

### Check active recordings

1. Dashboard or Queue reveals active recordings.
2. User can open streamer detail or live player.
3. Failure state explains what happened and links to recovery or diagnostics.

### Find video

1. User opens Library.
2. Search and filters reduce the grid.
3. Video cards make streamer, date, duration and processing state scannable.
4. Player errors are recoverable.

### Notification handling

1. User opens Notification Center.
2. User filters unread or severity.
3. User opens target route or marks read.
4. Mobile must present this as a sheet or full route, not a cramped popover.

### Mobile PWA use

1. User launches installed PWA.
2. Bottom navigation is thumb friendly.
3. Queue and notifications do not fight with bottom nav.
4. Push permission state and offline/reconnect state are clear.

## Information architecture audit

| Area | Current source | Audit result |
| --- | --- | --- |
| Primary navigation | Home, Streamers, Videos, Subscriptions, Settings | Good shape, but copy should consistently be Dashboard and Library if that is the product model |
| Global actions | Header shell, queue, notifications, theme, account | Correct concept, needs visual QA for density |
| Context routes | add streamer, detail, live, video | Correct route model and deep link support |
| Settings | SettingsView and panels | Too large, needs stronger section ownership and basic vs advanced split |
| Admin | AdminView and AdminPanel | Correct capsule for diagnostics, but AdminPanel is still 1,725 lines |
| Empty states | EmptyState exists | Need route by route consistency check |
| Loading states | LoadingSkeleton exists | Need systematic skeleton use on media and lists |
| Error states | PlayerError and notification states exist | Need common ErrorState pattern beyond player |

## Mobile, PWA and accessibility audit

- Mobile bottom navigation exists and safe area concepts are present.
- Core route files remain large enough that touch target and focus order must be verified manually rather than assumed.
- PWA flow has fewer registration paths, but installed app behavior, Android push and iOS Home Screen push are unverified in this environment.
- WCAG target is not complete until keyboard navigation, focus order, contrast and reduced motion are checked in a browser.

## Performance UX audit

- Route lazy loading exists.
- Large page and player files suggest chunk and interaction risks.
- Realtime store is better than scattered raw message watchers, but high event rate behavior still needs profiling.
- Video thumbnails and HLS/player initialization remain key perceived performance risks.
- Real LCP, INP and CLS were not measured yet.

## KAN2-002 IA decision summary

- Product target: StreamVault becomes a status first self hosted streaming and recording control center with media library polish, monitoring clarity and first class mobile PWA behavior.
- Desktop IA: keep sidebar primary navigation for Dashboard, Streamers, Library, Subscriptions and Settings. Keep Admin Diagnostics reachable but outside primary product navigation.
- Mobile IA: keep a five item bottom navigation and expose Jobs, Notifications, Add Streamer shortcuts, filters and recovery detail as sheets or context routes.
- Context routes: preserve Streamer Detail, Add Streamer, stored player, legacy watch route, Live Player, Setup, Onboarding and Login. Do not remove any route in the feature parity map.
- Progressive disclosure: surface status and recovery first, move raw diagnostics and advanced settings one level deeper.
- Accessibility and performance: status text must accompany color, panels need focus behavior, media and list routes need skeletons, players initialize lazily and mobile widths must avoid horizontal scroll.

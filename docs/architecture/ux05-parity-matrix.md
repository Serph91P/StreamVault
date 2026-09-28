# UX-05 parity and remaining-gates matrix (Run 44)

This matrix identifies the existing or changed implementation and its current local evidence. It does not claim provider, device, or unresolved backend-policy acceptance.

| UX-05 requirement | Implementation | Current evidence |
|---|---|---|
| Overview/live, recording, queue, activity and recent-history states | `app/frontend/src/views/HomeView.vue` | Full desktop/mobile Playwright: 80 passed, 30 existing skips; responsive and Axe routes included. |
| Backend recording auth mode, persisted priority including negative values, pending/blocked reason and partial warning | `HomeView.vue`, `src/services/recording-status.ts` | `tests/test_recording_active_status_contract.py` runs actual local FastAPI `/api/recording/active` over synthetic SQLite data; frontend facade/adapter test and 360/1440 browser test pass. |
| Unknown/error and retry do not masquerade as an empty active-recording result | `HomeView.vue` | `src/views/__tests__/HomeView.recording-status.spec.ts` exercises the actual Home consumer's rejected `recordingApi.getActiveRecordings` path and retry. |
| Streamer list/detail and add flow | `StreamersView.vue`, `StreamerDetailView.vue`, `AddStreamerView.vue`, existing cards/composables | Existing `mock-routes.spec.ts`, `ui-standards.spec.ts`, responsive matrix and full unit suite pass. |
| Add/import validation, duplicate and partial-result feedback | Existing `AddStreamerView.vue`, `TwitchImportForm.vue` and API/facade tests | Full 168-unit suite and desktop/mobile browser suite pass; no fake backend success was added by this run. |
| Filters/sorting/history | Existing `StreamersView.vue`, `VideosView.vue`, `stream-history.spec.ts` | Desktop history matrix passes through 360/1920; mobile project keeps its documented inherited skips. |
| Destructive actions and stale/delete behavior | Existing Streamer/video APIs, shared modal/form primitives, `useStreamers` tests | Full unit suite and browser overlay/focus tests pass. This run does not alter destructive API semantics. |
| Realtime ownership/reconnect/unmount | Existing `useRealtimeStore`, `HomeView` subscriptions/unsubscribe | Existing websocket/realtime unit coverage and full unit suite pass; no additional socket/poller was introduced. |

## Explicit remaining gates

- The implemented persisted priority contract accepts `-1000..1000`; the #842 text conflict requesting `0..1000` remains for the backend owner. UI preserves, rather than clamps, negative persisted values.
- The FastAPI/SQLite test is a local synthetic seam, not a provider canary. No Twitch/live credentials or production recording was used.
- Linux Chromium evidence does not constitute Android/iOS/PWA install, Firefox/WebKit, physical-device, or provider acceptance.

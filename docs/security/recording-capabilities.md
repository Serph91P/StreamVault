# Recording capabilities and settings confidentiality

The HTTP authorization boundary uses the existing current-owner policy, not the
role/scopes a credential used to have. JWTs are validated against the current
active owner and their own restricted claims. Legacy sessions and API keys derive
scopes from their current active owner; a revoked session/key is rejected. Existing
JWTs fail closed after owner deactivation or role downgrade. This does not add a
new JWT revocation store or role model.

## Registered capability matrix

All paths below are mounted by `create_app`. Dependencies run before the handler
and before its recording, file, provider, configuration or queue work.

| Operations | Required capability |
| --- | --- |
| POST `/api/recording/settings` | `recording:write` |
| POST `/api/recording/streamers/{streamer_id}` | `recording:write` |
| PUT `/api/streamers/streamer/{streamer_id}/settings` (nested and legacy recording/notification fields) | `recording:write` |
| POST `/api/recording/stop/{streamer_id}`, `/force-start/{streamer_id}` | `recording:write` |
| POST `/api/recording/cleanup/{streamer_id}`, `/cleanup/{streamer_id}/custom`, `/streamers/{streamer_id}/cleanup-policy` | `recording:write` |
| POST `/api/recording/recovery/scan` | `recording:write` (including dry runs on this write endpoint) |
| POST `/api/recordings/force-stop` (legacy alias) | `recording:write` |
| POST `/api/streamers/{username}`, DELETE `/api/streamers/{streamer_id}` | `recording:write` |
| DELETE `/api/streamers/{streamer_id}/streams`, `/api/streamers/{streamer_id}/streams/{stream_id}`, `/api/streams/{stream_id}` | `recording:write` |
| GET and POST `/api/settings` | Current active admin **and** `admin` scope (`require_admin_user`, as in #937) |
| POST `/api/settings/streamer/{streamer_id}`, `/test-notification`, `/test-websocket-notification` | Current active admin and `admin` scope |
| POST `/api/background-queue/tasks/enqueue`, `/metadata-generation`, `/thumbnail-generation`, `/file-cleanup` | Current active admin and `admin` scope |
| GET `/api/twitch/auth-url`; POST `/api/twitch/manual-token`, `/disconnect`, `/import-streamers` | Current active admin and `admin` scope |
| DELETE `/api/streamers/subscriptions`, `/subscriptions/{subscription_id}`; POST `/api/streamers/resubscribe-all` | Current active admin and `admin` scope |
| POST `/api/proxy/add`, `/{proxy_id}/toggle`, `/{proxy_id}/test`, `/{proxy_id}/update-priority`, `/config/update`; DELETE `/api/proxy/{proxy_id}` | Current active admin and `admin` scope |

An administrator JWT restricted to `recording:read` cannot write. An administrator
JWT explicitly restricted to `recording:read recording:write` can change recording
configuration but cannot read administrative credentials or change connection
configuration. Admin-owned API keys keep the existing administrative workflows;
non-admin-owned keys do not gain them. No new non-admin writer role is introduced.

### Reads and saves

`GET /api/settings` deliberately returns **403** to non-admin or scope-restricted
identities rather than returning masked notification/proxy URLs in the existing
secret-bearing response model. Authorized admins retain the original response
shape and full secret edit/readback workflow. Recording settings/status/presets,
channel notification projections, queue monitoring, masked proxy projections and
Twitch connection *status* remain readable under existing authentication. They do
not expose the global notification/proxy URL credentials or Twitch tokens.

An omitted `notification_url`, `http_proxy` or `https_proxy` on the administrative
save preserves its stored value. An explicit empty string (or the existing null
clear form) still clears it. There is no masked value sent by the server to be
mistaken for an edit or a deletion. This is intentionally not the broader global
partial-update contract tracked separately in #994.

### Callers and neighboring contracts

- `frontend/src/services/recording.ts` and `services/api-real.ts`: recording saves,
  stop/force-start, cleanup, settings, queue and Twitch import/link callers.
- `frontend/src/views/OnboardingWizardView.vue`, `StreamerDetailView.vue`, and
  `components/settings/ChannelSettingsPanel.vue`: global/nested channel saves.
- `frontend/src/components/settings/TwitchConnectionPanel.vue`,
  `ProxySettingsPanel.vue`, `NotificationSettingsPanel.vue` and admin notification
  tests: administrative connection/configuration callers.
- Legacy recording force-stop and both stream-delete aliases remain mounted and
  guarded. Unmounted `app/api/background_queue_endpoints.py` is not an alternate
  registered ingress (the mounted queue router is `app/routes/background_queue.py`).
- `/api/twitch/callback` remains provider-reachable; one-time session-bound OAuth
  state is #1027's separate producer contract. Removing the public `auth-url`
  exception does not change the callback or its local return-target allowlist.
- Queue payload validation/path confinement and actual manual worker outcomes are
  #1026/#1033. Admin admission does not certify arbitrary queued payloads as safe.
- Existing admin router guards, disabled Twitch priority/handoff, factory/session
  ownership and cleanup/retention selection semantics are unchanged.

## Regression proof

`tests/test_recording_capabilities.py` uses real `create_app`, middleware,
AuthService, ApiKeyService and fresh SQLite catalogs. It has no auth/session/DB
stubs or dependency overrides. It covers JWT and legacy Bearer/cookie credentials,
both API-key header forms, current-owner downgrade/deactivation, revoked opaque
credentials, scoped admin JWTs, anonymous access and cookie CSRF. Denial snapshots
include all catalog tables (except API-key usage telemetry), task state and files.
Allowed saves are checked against committed rows; cleanup deletes actual synthetic
old media and preserves recent media; manual connection storage uses real encryption
with only provider validation replaced. Admin queue tests prove actual admission,
not the separate worker result. Existing #937 admin tests remain required.

The registered-route test checks every mutation in the affected mounted routers,
including aliases and recovery, against the capability policy. Synthetic fixtures
block network connections and do not start application lifespan/provider services.
These tests do not claim live Twitch acceptance or a production recording run.

# Non-mock integration QA gate: t_3200d176

Task: N-QA-001B verify non-mock WebSocket HLS and push gates
Branch: feat/frontend-product-overhaul-final
Workspace: /opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final

## Summary

Result: BLOCKED, not a PASS recommendation.

A real non-mock backend is present in Docker, but the available environment does not include an authenticated browser/session or push-capable subscription state, so the WebSocket update, HLS playback, and push delivery gates cannot be accepted without faking results.

Existing mock-mode PASS artifacts were verified as present and read:

- `.hermes/frontend-visual-evidence/streamvault-frontend-qa-matrix.md`
- `.hermes/frontend-visual-evidence/qa-matrix-results.json`

Those artifacts state that mock-mode production preview passed the actionable visual/accessibility/performance gates, while real backend WebSocket, real HLS playback, and real push delivery remained outside that matrix.

## Environment discovery

Commands run from `/opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final`.

### Git/workspace

Command:

```bash
pwd && git status --short --branch && git branch --show-current && git remote -v
```

Exit code: 0

Relevant result:

- Branch: `feat/frontend-product-overhaul-final`
- Remote: `origin git@github.com:Serph91P/StreamVault.git`
- Worktree already had many modified/untracked files from the frontend overhaul and prior QA artifacts.
- No commit or push was performed.

### Running backend containers

Command:

```bash
docker inspect streamvault streamvault-develop --format '{{.Name}} image={{.Config.Image}} status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} networks={{range $k,$v := .NetworkSettings.Networks}}{{$k}}={{$v.IPAddress}} {{end}} ports={{json .NetworkSettings.Ports}}'
```

Exit code: 0

Result:

- `/streamvault image=frequency2098/streamvault:2.7.7 status=running health=healthy networks=pangolin-streamvault=10.200.5.194 streamvault_streamvault=172.22.0.3 ports={"7000/tcp":null}`
- `/streamvault-develop image=frequency2098/streamvault:2.10.0-dev status=running health=healthy networks=dedicated-streamvault-develop_streamvault_network=192.168.96.3 pangolin-streamvault-develop=10.200.5.227 ports={"7000/tcp":null}`

Host port probe:

- `127.0.0.1:7000` closed
- `127.0.0.1:8000` closed
- `127.0.0.1:5173` open
- `127.0.0.1:4173` open

The Docker app ports are not published to the host, but the backend is reachable from the host through Docker bridge IPs when the expected `Host: localhost` header is sent.

### Backend public/auth probes

Probe script: `/tmp/streamvault_non_mock_probe.py`
Raw JSON: `/tmp/streamvault_non_mock_probe.json`

Command:

```bash
uv run --with httpx --with websockets /tmp/streamvault_non_mock_probe.py | tee /tmp/streamvault_non_mock_probe.json
```

Exit code: 0

Key results:

For `streamvault` at `http://172.22.0.3:7000`:

- `GET /api/health`: 200, `{"status":"healthy", ... "database":"healthy"}`
- `GET /auth/check`: 200, `{"authenticated":false}`
- `GET /api/live/active`: 401, `{"error":"Authentication required","redirect":"/auth/login"}`
- `GET /api/push/vapid-public-key`: 401, `{"error":"Authentication required","redirect":"/auth/login"}`
- `GET /api/live/stream/no-session/playlist.m3u8`: 404, `{"detail":"Stream session not found"}`
- `WS /ws`: accepted then closed with code `4001`, reason `Authentication required`

For `streamvault-develop` at `http://192.168.96.3:7000`:

- `GET /api/health`: 200, `{"status":"healthy", ... "database":"healthy"}`
- `GET /auth/check`: 200, `{"authenticated":false}`
- `GET /api/live/active`: 401, `{"error":"Authentication required","redirect":"/auth/login"}`
- `GET /api/push/vapid-public-key`: 401, `{"error":"Authentication required","redirect":"/auth/login"}`
- `GET /api/live/stream/no-session/playlist.m3u8`: 404, `{"detail":"Stream session not found"}`
- `WS /ws`: accepted then closed with code `4001`, reason `Authentication required`

### Non-secret backend aggregate checks

Command:

```bash
for c in streamvault streamvault-develop; do
  docker exec "$c" sh -lc '
    command -v streamlink >/dev/null && streamlink --version | head -1 || echo streamlink missing
    command -v ffmpeg >/dev/null && ffmpeg -version | head -1 || echo ffmpeg missing
    python - <<"PY"
from app.database import SessionLocal
from app.models import User, PushSubscription, Streamer
from app.config.settings import get_settings
s=get_settings()
with SessionLocal() as db:
    print("admin_users=" + str(db.query(User).filter_by(is_admin=True).count()))
    print("streamers=" + str(db.query(Streamer).count()))
    print("active_push_subscriptions=" + str(db.query(PushSubscription).filter(PushSubscription.is_active.is_(True)).count()))
print("vapid_configured=" + str(bool(s.VAPID_PUBLIC_KEY and s.VAPID_PRIVATE_KEY)))
print("twitch_app_configured=" + str(bool(s.TWITCH_APP_ID and s.TWITCH_APP_SECRET)))
print("twitch_oauth_env_present=" + str(bool(getattr(s, "TWITCH_OAUTH_TOKEN", None))))
PY
  '
done
```

Exit code: 0

Sanitized result:

`streamvault`:

- `streamlink 8.2.1`
- `ffmpeg version 8.1.2`
- `admin_users=1`
- `streamers=5`
- `active_push_subscriptions=0`
- `vapid_configured=False`
- `twitch_app_configured=True`
- `twitch_oauth_env_present=True`

`streamvault-develop`:

- `streamlink 8.4.0`
- `ffmpeg version 8.1.2`
- `admin_users=1`
- `streamers=3`
- `active_push_subscriptions=0`
- `vapid_configured=False`
- `twitch_app_configured=True`
- `twitch_oauth_env_present=False`

## Gate verdicts

### WebSocket real backend updates

Verdict: BLOCKED.

Evidence:

- Both backends are healthy.
- Both `/auth/check` responses report `authenticated:false` for this QA context.
- Direct WebSocket connections to `/ws` close with code `4001`, reason `Authentication required`.
- The source enforces this in `app/middleware/auth.py:63`, where WebSocket connections require a session cookie or Bearer token.
- The test broadcast endpoint exists at `app/routes/settings.py:252`, but it cannot provide credible frontend delivery evidence without an authenticated browser WebSocket session.

Missing environment/human input:

- A valid non-mock authenticated browser session or test user credentials for the running backend.
- Permission to create a temporary QA admin/session in the running database, if credentials should not be shared.

### HLS playback

Verdict: BLOCKED.

Evidence:

- Live HLS endpoints are implemented in `app/routes/live.py`.
- `GET /api/live/active` returns 401 without authentication in both running containers.
- `GET /api/live/stream/no-session/playlist.m3u8` returns 404, proving there is no active test session with that ID and no usable playlist URL was available.
- `streamlink` and `ffmpeg` are installed in both containers, and streamers exist in both databases, but starting a real live stream requires an authenticated request to `/api/live/start/{streamer_name}` plus a live Twitch source.

Missing environment/human input:

- A valid authenticated non-mock session.
- A known currently-live streamer in the target backend, or a pre-existing live session playlist URL with playback token.
- Acceptance of the target container to test against, since both `streamvault` and `streamvault-develop` are running but neither is this workspace process.

### Push delivery or subscription flow

Verdict: BLOCKED.

Evidence:

- `GET /api/push/vapid-public-key` returns 401 without authentication in both running containers.
- Non-secret aggregate DB query reports `active_push_subscriptions=0` in both containers.
- Non-secret settings query reports `vapid_configured=False` in both containers.
- Frontend subscription code in `app/frontend/src/composables/usePWA.ts` requires a service worker registration, notification permission, a VAPID public key from `/api/push/vapid-public-key`, and a successful POST to `/api/push/subscribe`.

Missing environment/human input:

- A valid authenticated browser session.
- A secure/browser-accessible same-origin app URL suitable for service worker and PushManager testing.
- VAPID keys configured or confirmed auto-generation path working in the chosen backend.
- At least one real browser/device subscription, or permission to create one during QA.

## Recommendation

Do not unblock/accept root N-QA-001 as a non-mock PASS yet.

Stable blocker handoff:

- Backend containers are healthy and have DB connectivity, Streamlink, and FFmpeg.
- This QA run did not have credentials/session/device state to exercise authenticated WebSocket delivery, authenticated live HLS start/playback, or real push subscription/delivery.
- Push is additionally blocked by `active_push_subscriptions=0` and `vapid_configured=False` in both discovered containers.

To finish the non-mock gate, provide one of these:

1. A disposable QA login/session for the selected backend plus the expected externally reachable URL.
2. Approval to create a temporary QA admin/session and browser push subscription in the selected running backend.
3. A pre-existing authenticated session cookie/API flow plus a currently-live streamer or active HLS playlist URL with token.

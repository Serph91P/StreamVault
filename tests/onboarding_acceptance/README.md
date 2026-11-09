# Onboarding first-channel acceptance (#995)

The regression adds the first channel through the **built REAL wizard**, actual
application factory, registered `/api/streamers/{username}` route, `StreamerService`
and repository commit. It checks a new SQLite session, a fresh production GET and
page reload, not an HTTP fulfillment or in-memory creation stub.

```sh
cd app/frontend
npm ci
node scripts/build-artifact-provenance.mjs build --mode real
cd ../..
python3 tests/onboarding_acceptance/run.py --output "$TMPDIR/issue995-evidence"
```

Prerequisites: Docker, the already-installed local image
`frequency2098/streamvault:2.24.0-dev` (dependency runtime only; candidate source and
REAL dist are streamed over stdin), and the frontend's matching Playwright Chromium.
Use `PLAYWRIGHT_BROWSERS_PATH` for a writable browser cache when necessary.
The runner verifies REAL build source/artifact provenance before use. It uses a
unique `--rm` container with `/scratch` tmpfs and synthetic SQLite only. It shares
the existing `hermes-gateway-developer` network namespace for local browser access;
no application volume or host database is mounted. The owned container and database
are removed on success and failure; evidence is retained in `--output`.

## Isolation and limits

- Real auth middleware and login with an ephemeral, generated synthetic admin.
  No existing credentials, `.env`, databases, provider tokens or production data.
- Production lifespan/background jobs are disabled. Provider user lookup, live
  status, EventSub subscription and image download I/O are synthetic test adapters.
  `get_user_data`, creation, DB commit, validation and all business routes are real.
- All backend outbound socket connects are forbidden; browser requests outside the
  local test origin are aborted. No real provider contact or provider acceptance claim.
- Missing, null, malformed, array and string bodies are rejected by the actual
  registered route; blank/invalid names and provider rejection produce no channel.
- Browser transport corruption exercises real 422 validation. Browser abort models
  a network failure. No API response is fulfilled. Every failure preserves input,
  leaves the success list empty and does not complete onboarding.
- A controllably delayed provider proves the pending input/button and submit guard;
  retry after failures creates exactly one channel. A new DB session, fresh GET and
  reload confirm persistence. Seeded global defaults remain untouched. Per-channel
  default selection belongs to #996, not this regression.
- This does not test real Twitch, production startup, devices, PWA or deployment.

Fast component regression (real Vue view and buttons, network boundary mocked):

```sh
cd app/frontend
npm run test:unit -- src/views/__tests__/OnboardingWizardView.streamers.spec.ts
```

The component suite protects the exact minimal `{}` JSON request/session, trim/@
normalization, only-confirmed list updates, HTTP/network failures, delayed duplicate
submits, retry and draft preservation through manual step navigation. The separate
full-stack runner above is the persistence proof; it is intentionally opt-in and
requires the isolated Docker runtime, not an extra production seam or CI waiver.

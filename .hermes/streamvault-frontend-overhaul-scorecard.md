# StreamVault frontend overhaul scorecard

Date: 2026-07-07
Branch: feat/frontend-product-overhaul-final

## Summary

This branch is ready to push as a develop image candidate for Max to test on real infrastructure. It is not marked as a fully complete overhaul because real browser Push subscription and delivery cannot be verified in the Hermes headless/Xvfb environment.

## Scorecard

| Area | Status | UX | Visual polish | Density | Mobile | Accessibility | Performance confidence | Evidence | Open risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Dashboard | implemented and visually verified | 4 | 4 | 4 | 4 | 4 | 3 | viewport matrix and local checks | none known |
| Streamers | implemented and visually verified | 4 | 4 | 4 | 4 | 4 | 3 | streamers screenshots and local checks | none known |
| Streamer Detail | implemented and visually verified | 4 | 4 | 4 | 4 | 4 | 3 | overview, videos, settings and events screenshots | none known |
| Videos / Library | implemented and visually verified | 4 | 4 | 4 | 4 | 4 | 3 | library screenshots and card QA | none known |
| Players | implemented and functionally verified | 4 | 4 | 4 | 4 | 4 | 4 | HLS non-mock PASS and player screenshots | real device playback still useful |
| Notification Center | implemented and visually verified | 4 | 4 | 4 | 4 | 4 | 3 | notification center screenshots and script checks | none known |
| Settings | implemented and visually verified | 4 | 4 | 4 | 4 | 4 | 3 | settings screenshots and source checks | none known |
| PWA / Mobile | blocked with reason | 4 | 4 | 4 | 4 | 4 | 3 | mobile evidence and VAPID server PASS | real browser Push subscription/delivery pending |
| Admin Diagnostics | intentionally admin-only | 4 | 4 | 4 | 4 | 4 | 3 | admin diagnostics QA screenshots | none known |
| Non-mock WebSocket | implemented and functionally verified | 4 | 4 | 4 | 4 | 4 | 4 | `.hermes/non-mock-authorized-qa-results.json` | none known |
| Non-mock HLS | implemented and functionally verified | 4 | 4 | 4 | 4 | 4 | 4 | `.hermes/non-mock-authorized-qa-results.json` | depends on live source availability |
| Browser Push | blocked with reason | 3 | 4 | 4 | 4 | 4 | 3 | `.hermes/browser-push-qa-summary.md` | needs real Chrome/Edge or device |

## Verification commands

Passed locally:

```bash
cd app/frontend && npm run lint:tokens && npm run type-check && npm run build && npm run lint
uv run --with-requirements requirements.txt --with pytest --with pytest-asyncio --with httpx python -m pytest tests/ -q --tb=short
uv run --with-requirements requirements.txt --with ruff ruff check app/
uv run --with-requirements requirements.txt --with ruff ruff format --check app/
uv run --with-requirements requirements.txt python -m app.migrations_init
```

Docker image validation was attempted locally and blocked by host tooling:

```bash
docker build -f docker/Dockerfile -t streamvault:local-overhaul-check .
# failed because legacy Docker builder does not support Dockerfile --mount
DOCKER_BUILDKIT=1 docker build -f docker/Dockerfile -t streamvault:local-overhaul-check .
# failed because local Docker buildx component is missing or broken
```

GitHub CI should run the Docker Buildx workflow after PR creation.

## Remaining manual test after image build

Max should test the remaining Push gate on the newly built image:

1. Open the deployed StreamVault URL in a real non-incognito Chrome or Edge profile.
2. Sign in.
3. Go to Settings, PWA / Push.
4. Confirm install/service-worker state is ready.
5. Allow browser notifications when prompted.
6. Click the Subscribe or Enable Push action.
7. Run the in-app test notification action.
8. Confirm the notification arrives and opens the expected target route when clicked.
9. If it fails, capture browser console errors, permission state, URL, browser, OS and the response from `/api/push/debug`.

## Gate decision

Ready for PR and develop image build as a test candidate. Not final-complete until real browser Push subscription and delivery passes or Max accepts that remaining device/browser gate.

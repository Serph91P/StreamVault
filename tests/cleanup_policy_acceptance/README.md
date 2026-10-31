# Cleanup policy persistence acceptance (#947)

This exercises the built **REAL** UI, Pinia, recording services, production app
factory/routers and a disposable SQLite database. The production background
lifespan is disabled: no recorder, provider or cleanup job runs. It creates only
synthetic identities. Generated login material and backend logs are discarded.

```sh
uv sync --locked --all-groups
cd app/frontend
npm ci
npx playwright install --with-deps chromium
node scripts/build-artifact-provenance.mjs build --mode real
cd ../..
TMPDIR=/path/to/scratch uv run python tests/cleanup_policy_acceptance/run.py --output /path/to/evidence
```

Twelve desktop/mobile journeys cover global, custom channel and inherited channel
policies, each with one HTTP 500 or aborted POST followed by an unchanged retry.
Only the deliberately failed POST is fulfilled/aborted; successful business
requests use the real backend. Assertions compare independent database sessions
and Pinia state before/after failure, keep the draft and dialog open, reject
success UI, check identical retry payloads, and reload the persisted policy.
Any cleanup endpoint invocation fails the test. No recording or file is deleted.

`result.json`, failed-state screenshots and build provenance are saved in the
output directory. Backend process and its synthetic database are removed even
when the journey fails. The workflow runs this separately from existing gates.

`--frontend /path/to/frontend` selects an already built REAL frontend for a
bounded test integration. Run the script from that integration's source tree to
exercise its backend as well; this does not merge or publish that integration.

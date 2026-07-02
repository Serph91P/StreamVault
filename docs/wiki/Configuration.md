# Configuration

## Required environment variables

| Variable | Purpose |
| --- | --- |
| `TWITCH_APP_ID` | Twitch application client ID |
| `TWITCH_APP_SECRET` | Twitch application client secret |
| `BASE_URL` | Public HTTPS URL for StreamVault |
| `EVENTSUB_SECRET` | Random secret used for Twitch webhook validation |
| `POSTGRES_USER` | PostgreSQL user |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | PostgreSQL database name |

## Optional browser token

Use **Settings > Twitch Connection** to store a Twitch browser token. StreamVault encrypts the token in the database. `TWITCH_OAUTH_TOKEN` can still be used as a fallback.

The browser token enables higher quality recording variants such as 1440p, H.265, and AV1 when Twitch provides them.

## Recording settings

Configure recording quality, filename templates, cleanup policy, proxy usage, and codec preferences globally or per streamer.

## Notifications

StreamVault supports external notification URLs through Apprise and browser push notifications. Configure them in the web interface under settings.

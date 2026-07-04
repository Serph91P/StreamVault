<div align="center">

# StreamVault

### Self-hosted Twitch recorder, live player, and media library

StreamVault records Twitch streams automatically, keeps the recordings organized with metadata and artwork, and provides a modern web app for watching, managing, and sharing your archive.

[![Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D?style=flat-square&logo=vue.js&logoColor=white)](https://vuejs.org)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

[Features](#features) | [Quick start](#quick-start) | [Configuration](#configuration) | [Documentation](#documentation) | [Development](#development)

</div>

---

## Features

### Twitch recording

- EventSub based live detection for automatic recording.
- Manual recording controls from the web interface.
- Streamlink based downloads with configurable quality, codec, and proxy settings.
- H.265, AV1, and 1440p recording support when a Twitch browser token is configured.
- Safe handling for long streams, recording state recovery, and orphan cleanup.

### Native live playback

- Watch live Twitch streams inside StreamVault through `/live/:streamer`.
- Streamlink and FFmpeg create HLS output that is played by bundled `hls.js`.
- Authenticated playlist and segment requests use playback tokens.
- Live playback uses browser compatible H.264 where needed while recordings can keep higher quality codec preferences.
- Temporary live segments are stored in `/tmp/streamvault-live` and cleaned up automatically.

### Media library

- PWA frontend for streamers, recordings, live playback, settings, and admin tools.
- Metadata, NFO files, thumbnails, banners, posters, fanart, and chapter files.
- Bulk video selection and deletion with confirmation.
- Media server friendly output for Plex, Emby, Jellyfin, Kodi, and similar libraries.

### Operations

- Docker Compose deployment with PostgreSQL and persistent volumes.
- Session based authentication and API key support for automation.
- Notifications through Apprise plus web push notifications.
- Cleanup policies by age, size, count, and per streamer overrides.
- GitHub Actions for tests, security scanning, and Docker image builds.

## Quick start

### Requirements

- Docker and Docker Compose.
- A public HTTPS URL for Twitch EventSub webhooks.
- A Twitch developer application with client ID and client secret.
- Enough storage for recordings. A 4 hour 1080p stream can easily use 8 to 15 GB.

### 1. Clone the repository

```bash
git clone https://github.com/Serph91P/StreamVault.git
cd StreamVault
```

### 2. Configure your environment

Edit the repository `.env` file and set at least these values:

```env
TWITCH_APP_ID=your_twitch_client_id
TWITCH_APP_SECRET=your_twitch_client_secret
BASE_URL=https://streamvault.example.com
EVENTSUB_SECRET=replace_with_a_random_secret
POSTGRES_USER=streamvault
POSTGRES_PASSWORD=replace_with_a_strong_password
POSTGRES_DB=streamvault
TZ=Europe/Berlin
```

Generate a webhook secret with:

```bash
openssl rand -hex 32
```

### 3. Start StreamVault

```bash
docker compose -f docker/docker-compose.yml up -d
```

Open your `BASE_URL` in the browser. The container exposes port `7000` internally and through the compose file.

## Configuration

### Twitch application

Create an application in the [Twitch developer console](https://dev.twitch.tv/console/apps):

- OAuth redirect URL: `https://your-domain.example/auth/callback`
- Category: Application Integration

### Browser token for higher quality recordings

StreamVault can store a Twitch browser token through **Settings > Twitch Connection**. The token is encrypted in the database and the `TWITCH_OAUTH_TOKEN` environment variable remains available as a fallback.

Use a browser token when you want:

- 1440p60 recording when available.
- H.265 or AV1 recording when available.
- Better compression for archived files.

Live browser playback intentionally selects compatible codecs so playback works reliably in hls.js and browser Media Source Extensions.

### Volumes

The compose file stores data in these locations:

| Path or volume | Purpose |
| --- | --- |
| `./recordings` | Recorded video files and generated media files |
| `app_data` | Application data |
| `app_logs` | Application logs |
| `db_data` | PostgreSQL database data |
| `./config/streamlink` | Streamlink configuration files |
| `/tmp/streamvault-live` | Temporary HLS files for native live playback |

## Documentation

Repository docs:

- [User guide](docs/USER_GUIDE.md)
- [Browser token setup](docs/BROWSER_TOKEN_SETUP.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Wiki source](docs/wiki/Home.md)

Wiki pages prepared in this repository:

- [Home](docs/wiki/Home.md)
- [Installation](docs/wiki/Installation.md)
- [Configuration](docs/wiki/Configuration.md)
- [Usage](docs/wiki/Usage.md)
- [Live Streaming](docs/wiki/Live-Streaming.md)
- [Development](docs/wiki/Development.md)
- [Troubleshooting](docs/wiki/Troubleshooting.md)

## API

Interactive API documentation is available from a running instance:

- Swagger UI: `/docs`
- OpenAPI schema: `/openapi.json`

Common API groups include:

| Area | Example paths |
| --- | --- |
| Streamers | `/api/streamers` |
| Recordings | `/api/recording/start/{id}`, `/api/recording/stop/{id}` |
| Videos | `/api/videos` |
| Live playback | `/api/live/start/{streamer}`, `/api/live/{session_id}/playlist.m3u8` |
| Settings | `/api/settings` |
| Twitch auth | `/api/twitch-auth` |
| Admin and health | `/health`, `/api/admin/test/health` |

## Development

Backend:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd app/frontend
npm install
npm run dev
```

Checks used by CI:

```bash
ruff format --check app tests
ruff check app tests
pytest tests/ -q
cd app/frontend
npm run lint:tokens
npm run type-check
npm run build
```

## Tech stack

- FastAPI, SQLAlchemy, PostgreSQL, Alembic style migrations.
- Vue 3, TypeScript, Vite, Pinia, SCSS, hls.js.
- Streamlink and FFmpeg for recording and live HLS playback.
- Docker Compose for production style deployment.
- GitHub Actions, Bandit, pip-audit, npm audit, Gitleaks, Trivy, Hadolint, and CodeQL for automation and scanning.

## Support

Use [GitHub Issues](https://github.com/Serph91P/StreamVault/issues) for bugs and feature requests. Include the StreamVault version, deployment method, relevant logs, and clear reproduction steps.

## License

StreamVault is licensed under the MIT License. See [LICENSE](LICENSE).

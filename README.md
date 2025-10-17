# StreamVault 📹

Self‑hosted autonomous livestream recorder & media library builder for Twitch (extensible to other platforms). StreamVault watches configured channels, records streams with Streamlink, performs post‑processing, generates rich metadata/artwork, and serves everything through a modern FastAPI + Vue 3 (PWA) interface.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-green.svg)](https://fastapi.tiangolo.com)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.3+-4FC08D.svg)](https://vuejs.org)
[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
[![GitHub release](https://img.shields.io/github/v/release/Serph91P/StreamVault?include_prereleases)](https://github.com/Serph91P/StreamVault/releases)

## ✨ Key Features

### Recording & Capture
* Auto detection & start when a streamer goes live (Twitch EventSub)
* Streamlink based capture with quality selection & very long stream segmentation (24h+ safe rollover)
* Robust proxy support (HTTP / HTTPS) with latency + audio sync mitigation
* Graceful recovery: startup recovery scans and failed task requeue logic

### Streamer & Policy Management
* Per‑streamer recording rules, quality, cleanup policies, templates
* Bulk enable/disable & status dashboard
* Automatic category tracking (used for chapters & metadata enrichment)

### Web UI / PWA
* Responsive Vue 3 interface installable as PWA
* Real‑time WebSocket updates (recording state, queue progress)
* Background queue monitor & admin health test suite
* Session cookie fixes (2025) ensure stable login + PWA notifications

### Post‑Processing & Metadata
* Dependency‑driven async task queue (chapters, remux, validation, thumbnails)
* Multi‑format chapter generation (.vtt/.xml) & automatic episode numbering
* Artwork pipeline with centralized store + local compatibility copies
* Safe metadata paths for Plex / Emby / Jellyfin / Kodi

### Media Server Integration
* NFO generation with artwork (poster, banner, fanart) and chapters
* Year‑Month season structuring (YYYYMM) & episode naming patterns
* Intelligent relative path resolution for artwork under hidden .media directory

### Notifications & Automation
* Apprise integration (multi‑provider) + web push (auto VAPID key generation)
* Configurable cleanup: age / size / count across per‑streamer or global policies
* Secure REST API for external automation

### Reliability & Maintenance
* Automatic database migrations at startup (idempotent)
* Image migration & refresh services (legacy layout → new structure)
* Log rotation & pruning
* Graceful shutdown of recording & queue workers

## 🚀 Quick Start

### Prerequisites

* Docker & Docker Compose
* ~1 GB RAM (2 GB recommended) for core services
* Adequate disk (recordings: 2–8 GB / hr @ 1080p; plan ahead)
* Public HTTPS endpoint (reverse proxy) for Twitch EventSub (TLS mandatory)

Why HTTPS? Twitch requires valid, publicly reachable HTTPS for webhook verification. Use Let’s Encrypt via Traefik, Caddy, Nginx, or a Cloudflare Tunnel.

### 1. Obtain Compose & Env Template

Clone the repository (recommended) to get versioned updates:

```bash
git clone https://github.com/Serph91P/StreamVault.git
cd StreamVault
cp .env.example .env  # if provided / else create manually
```

Or fetch only the Docker assets from the `docker/` directory if you prefer a slim deployment layout.

### 2. Environment Configuration

Edit `.env`:

```env
TWITCH_APP_ID=your_twitch_client_id
TWITCH_APP_SECRET=your_twitch_client_secret
BASE_URL=https://your-domain.com        # Public URL (HTTPS!)
EVENTSUB_SECRET=choose_random_string    # Used to verify EventSub payloads
POSTGRES_USER=streamvault
POSTGRES_PASSWORD=strong_password
POSTGRES_DB=streamvault
```

Optionally add proxy variables (HTTP_PROXY / HTTPS_PROXY) or adjust time zone (TZ). VAPID keys for push are auto‑generated if not provided.

### 3. Create Twitch Application

1. Visit [Twitch Developer Console](https://dev.twitch.tv/console/apps)
2. Click **"Create Application"**
3. Fill in the application details:
   - **Name**: StreamVault (or your preferred name)
   - **OAuth Redirect URLs**: `https://your-domain.com/auth/callback`
   - **Category**: Application Integration
4. Copy the **Client ID** and **Client Secret**
5. Add them to your `.env` file

### 4. Reverse Proxy (Example Nginx)

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    
    location / {
        proxy_pass http://localhost:7000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### 5. Launch

```bash
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml logs -f app
```

Visit `https://your-domain.com` (through your proxy). Internally the app listens on port 7000.

Storage note: A 4h 1080p stream can exceed 10 GB. Configure cleanup early.

## 📖 Migrations & Schema

Migrations run automatically at startup (idempotent). No manual scripts are required. Logs clearly show applied / skipped migrations. If a migration partially fails the app continues (degraded) and warnings are emitted. Columns or tables that already exist are skipped silently.

## ⚙️ Configuration Examples

### Recording Settings

StreamVault offers extensive recording configuration options:

- **Output Directory**: Where recordings are stored
- **Filename Template**: Customize file naming with variables like `{streamer}`, `{title}`, `{date}`
- **Quality Settings**: Choose recording quality (best, worst, 1080p, 720p, etc.)
- **Remux to MP4**: Automatically convert recordings to MP4 format

### Cleanup Policies

Automatic cleanup helps manage storage:

```json
{
  "max_age_days": 30,
  "max_size_gb": 100,
  "max_files": 50,
  "enabled": true
}
```

### Proxy Configuration

For users requiring proxy support:

- Configure HTTP/HTTPS proxies in settings
- Automatic audio-sync optimizations for proxy connections
- Enhanced buffering and retry logic for stable recordings

## 🌐 API Reference (Excerpt)

StreamVault provides a comprehensive REST API:

```bash
# Streamer Management
GET /api/streamers                    # Get all streamers
POST /api/streamers                   # Add a new streamer
PUT /api/streamers/{streamer_id}      # Update streamer settings

# Recording Control
POST /api/recording/start/{streamer_id}  # Start recording manually
POST /api/recording/stop/{streamer_id}   # Stop recording

# Video Management
GET /api/videos                       # Get all videos
GET /api/videos/stream/{streamer_name}/{filename}  # Stream a video
DELETE /api/videos/{video_id}         # Delete a video

# Background Queue Management
GET /api/background-queue/stats       # Get queue statistics
GET /api/background-queue/active-tasks  # Get active tasks
GET /api/background-queue/stream/{stream_id}/tasks  # Get tasks for stream
POST /api/background-queue/cancel-stream/{stream_id}  # Cancel stream tasks

# Admin & Testing
GET /api/admin/test/health           # System health check
POST /api/admin/test/recording-workflow  # Test recording workflow
GET /api/admin/test/logs             # Get system logs
```

Interactive OpenAPI docs: `https://your-domain.com/docs`

## 🛠️ Development

### Local Development Setup

1. Backend
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

2. Frontend (if developing UI separately)
```bash
cd app/frontend
npm install
npm run dev
```

### Project Structure (Simplified)

```
streamvault/
├── app/
│   ├── frontend/          # Vue.js frontend application
│   │   ├── src/           # Vue.js source code
│   │   │   ├── components/ # Vue components including BackgroundQueueMonitor
│   │   │   ├── composables/ # Vue composables (useBackgroundQueue, useWebSocket)
│   │   │   └── styles/    # SCSS styles
│   │   └── dist/          # Built frontend assets
│   ├── api/               # API endpoints
│   │   └── background_queue_endpoints.py # Background queue API
│   ├── routes/            # FastAPI route handlers
│   ├── services/          # Business logic services
│   │   ├── recording/     # Recording service modules
│   │   │   ├── config_manager.py      # Configuration management
│   │   │   ├── process_manager.py     # Process management
│   │   │   ├── recording_service.py   # Main recording service
│   │   │   └── notification_manager.py # Notifications
│   │   ├── background_queue_service.py # Background processing
│   │   ├── task_dependency_manager.py  # Task dependency management
│   │   ├── recording_task_factory.py   # Task chain factory
│   │   ├── post_processing_task_handlers.py # Task handlers
│   │   ├── metadata_service.py         # Metadata generation
│   │   └── thumbnail_service.py        # Thumbnail generation
│   ├── utils/             # Utility functions
│   │   ├── ffmpeg_utils.py           # FFmpeg operations
│   │   ├── streamlink_utils.py       # Streamlink utilities
│   │   └── mp4box_utils.py           # MP4Box integration
│   ├── models/            # Database models
│   ├── schemas/           # Pydantic schemas
│   └── migrations/        # Database migrations
├── docs/                  # Documentation
│   ├── admin_test_system.md          # Admin system docs
│   ├── recording_logging_integration.md # Logging docs
│   └── mp4box_integration.md         # MP4Box docs
├── recordings/            # Default recordings directory
├── docker-compose.yml     # Docker configuration
└── requirements.txt       # Python dependencies
```

### Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Quality

Recommended (run manually as needed): flake8, black, isort, mypy, bandit, safety. Integrate via pre‑commit or CI.

## 🔧 Configuration Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TWITCH_APP_ID` | Twitch application client ID | - | Yes |
| `TWITCH_APP_SECRET` | Twitch application client secret | - | Yes |
| `BASE_URL` | Application base URL (must be HTTPS with valid certificate) | - | Yes |
| `EVENTSUB_SECRET` | Secret for Twitch EventSub webhook validation | (Random if omitted) | No |
| `POSTGRES_USER` | PostgreSQL username | `streamvault` | Yes |
| `POSTGRES_PASSWORD` | PostgreSQL password | - | Yes |
| `POSTGRES_DB` | PostgreSQL database name | `streamvault` | Yes |

Note: Push / Apprise targets are configured through the UI; VAPID keys auto‑generate on first start if absent.

### Docker Compose Services

- **app**: Main FastAPI application with Vue.js frontend (runs on port 7000)
- **db**: PostgreSQL database with health checks

## 📊 System Requirements

### Minimum Requirements
- **CPU**: 2 cores
- **RAM**: 1GB for application
- **Storage**: 50GB+ (recordings grow quickly - 2-8GB per hour per stream)
- **Network**: Stable internet connection

### Recommended Requirements
- **CPU**: 4+ cores
- **RAM**: 2GB for application
- **Storage**: 1TB+ SSD (recordings can accumulate very quickly)
- **Network**: High-speed internet for multiple concurrent recordings

> **Storage Warning**: Stream recordings can grow very large very quickly. A single 4-hour stream in 1080p can be 8-15GB. Plan your storage accordingly and consider implementing cleanup policies.

## 🤝 Community & Support

- **Issues**: [GitHub Issues](https://github.com/Serph91P/StreamVault/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Serph91P/StreamVault/discussions)
- **Wiki**: [Project Wiki](https://github.com/Serph91P/StreamVault/wiki)

## 🔄 Background Processing System

StreamVault includes a sophisticated background processing system that handles post-recording tasks efficiently:

### Task Dependencies
- **Metadata Generation**: Extracts stream information and creates NFO files
- **Chapter Generation**: Creates chapter files from stream events
- **MP4 Remux**: Converts TS files to MP4 with embedded metadata
- **MP4 Validation**: Ensures file integrity before cleanup
- **Thumbnail Generation**: Creates thumbnails from video content
- **Intelligent Cleanup**: Safely removes temporary files after validation

### Queue Management
- **Real-time Monitoring**: Live task progress tracking in the web interface
- **Priority System**: Critical tasks (validation) run before optional tasks (thumbnails)
- **Retry Logic**: Automatic retry for failed tasks with exponential backoff
- **Dependency Resolution**: Ensures tasks execute in the correct order
- **Graceful Shutdown**: Properly handles application restarts without data loss

### Media Server Integration
- **Plex/Emby/Jellyfin**: Automatic NFO file generation with proper metadata
- **Chapter Support**: Multiple chapter formats (.vtt, .xml) for media players
- **Thumbnail Creation**: Multiple thumbnail formats for different media servers
- **Season Organization**: Automatic year-month based season structure

## 📋 Roadmap

- [x] **Background Processing System**: Dependency-based task queue ✅
- [x] **Media Server Integration**: Plex, Emby, Jellyfin, Kodi support ✅
- [x] **Chapter Support**: Automatic chapter generation from stream events ✅
- [x] **Admin Test System**: Comprehensive health checks and maintenance ✅
- [ ] **Cloud Storage Integration**: S3, Google Drive, Dropbox
- [ ] **Advanced Analytics**: Recording statistics and insights
- [ ] **Stream Highlights**: Automatic highlight detection and extraction

## 🙏 Acknowledgments

- [Streamlink](https://streamlink.github.io/) - The backbone of our recording functionality
- [FastAPI](https://fastapi.tiangolo.com/) - Modern, fast web framework for APIs
- [Vue.js](https://vuejs.org/) - Progressive JavaScript framework for the frontend
- [Twitch API](https://dev.twitch.tv/docs/api/) - Stream data and webhooks
- [FFmpeg](https://ffmpeg.org/) - Video processing and conversion
- [MP4Box](https://gpac.wp.imt.fr/mp4box/) - Advanced MP4 metadata processing
- [PostgreSQL](https://www.postgresql.org/) - Robust database system
- [Docker](https://www.docker.com/) - Containerization platform

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2025 StreamVault Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

**StreamVault** – Never miss a stream again.

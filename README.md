# StreamVault

Self-hosted autonomous livestream recorder and media library builder for Twitch. StreamVault watches configured channels, records streams with Streamlink, performs post-processing, generates rich metadata and artwork, and serves everything through a modern FastAPI + Vue 3 PWA interface.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-green.svg)](https://fastapi.tiangolo.com)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.3+-4FC08D.svg)](https://vuejs.org)
[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
[![GitHub release](https://img.shields.io/github/v/release/Serph91P/StreamVault?include_prereleases)](https://github.com/Serph91P/StreamVault/releases)

## Key Features

### Recording and Capture
- Automatic detection and recording when streamers go live via Twitch EventSub webhooks
- Streamlink-based capture with quality selection and multi-hour stream segmentation (24h+ safe rollover)
- Robust HTTP/HTTPS proxy support with automatic audio synchronization and latency mitigation
- Graceful recovery with startup recovery scans and failed task requeue logic
- H.265/HEVC and AV1 codec support with browser token authentication
- 1440p60 recording quality support for compatible streams
- Configurable recording quality per streamer (best, 1080p, 720p, etc.)
- Manual recording start/stop control via web interface or API

### Streamer and Policy Management
- Per-streamer recording rules, quality settings, and cleanup policies
- Customizable filename templates with variables (streamer, date, time, category, title)
- Bulk enable/disable streamer recording
- Status dashboard showing live status and recording state
- Automatic category tracking for chapters and metadata enrichment
- Import followed channels directly from your Twitch account

### Web UI and PWA
- Responsive Vue 3 interface installable as Progressive Web App (PWA)
- Real-time WebSocket updates for recording state and queue progress
- Touch-optimized video player with custom controls
- Dark and light theme support with automatic system detection
- Background queue monitor showing active post-processing tasks
- Admin health check system for testing all components
- Session-based authentication with secure cookie handling

### Post-Processing and Metadata
- Dependency-driven async task queue for post-processing operations
- Multi-format chapter generation (VTT and XML) with automatic episode numbering
- Thumbnail generation from video content with multiple quality options
- Artwork pipeline with centralized storage and local compatibility copies
- Safe metadata paths for Plex, Emby, Jellyfin, and Kodi integration
- Automatic remuxing from TS to MP4 format with embedded metadata
- File validation to ensure recording integrity before cleanup

### Media Server Integration
- NFO file generation with complete metadata (title, description, date, categories)
- Artwork support including poster, banner, and fanart images
- Chapter file export in multiple formats for different media players
- Year-Month season structuring (YYYYMM format) for automatic organization
- Episode naming patterns compatible with media server conventions
- Intelligent relative path resolution for artwork references

### Notifications and Automation
- Apprise integration supporting 100+ notification services (Discord, Telegram, Slack, Ntfy, Email, and more)
- Web push notifications with automatic VAPID key generation
- Configurable event notifications:
  - Stream online/offline/update events
  - Recording started/failed/completed events
  - Favorite category detection
- Per-event notification toggles for fine-grained control
- Test notification system to verify configuration

### Storage Management
- Configurable automatic cleanup policies by age, size, or file count
- Global and per-streamer cleanup configuration
- Safe cleanup that only removes validated recordings
- Storage usage tracking and monitoring
- Temporary file cleanup after successful post-processing

### Reliability and Maintenance
- Automatic database migrations at startup (idempotent and safe)
- Image migration and refresh services for legacy layout updates
- Comprehensive logging with configurable verbosity levels
- Log rotation and pruning to prevent disk usage issues
- Graceful shutdown of recording and queue workers
- Process recovery on application restart
- Health check endpoints for monitoring

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Minimum 1 GB RAM (2 GB recommended)
- At least 50 GB storage (recordings require 2-8 GB per hour at 1080p)
- Public HTTPS endpoint with valid certificate (for Twitch EventSub webhooks)
- Twitch Developer Application (free, instructions below)

**Why HTTPS?** Twitch requires valid, publicly reachable HTTPS for webhook verification. Use Let's Encrypt via Traefik, Caddy, Nginx, or a Cloudflare Tunnel.

### Installation Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/Serph91P/StreamVault.git
   cd StreamVault
   ```

2. Copy environment template:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` with your configuration (see Configuration section below)

4. Start the application:
   ```bash
   docker compose -f docker/docker-compose.yml up -d
   ```

5. Access web interface at `https://your-domain.com` (port 7000 internally)

### Creating a Twitch Application

1. Visit [Twitch Developer Console](https://dev.twitch.tv/console/apps)
2. Click "Create Application"
3. Fill in the details:
   - **Name**: StreamVault (or your preferred name)
   - **OAuth Redirect URLs**: `https://your-domain.com/auth/callback`
   - **Category**: Application Integration
4. Copy the Client ID and generate a Client Secret
5. Add them to your `.env` file

### Environment Configuration

Edit `.env` with the following required settings:

```env
# Twitch API Configuration
TWITCH_APP_ID=your_twitch_client_id
TWITCH_APP_SECRET=your_twitch_client_secret
TWITCH_OAUTH_TOKEN=                    # Optional - enables H.265/1440p quality

# Application URLs
BASE_URL=https://your-domain.com       # Must be HTTPS with valid certificate
EVENTSUB_SECRET=random_secure_string   # Random string for webhook verification

# Database Configuration
POSTGRES_USER=streamvault
POSTGRES_PASSWORD=strong_secure_password
POSTGRES_DB=streamvault

# Optional Settings
TZ=Europe/Berlin                       # Your timezone
LOG_LEVEL=INFO                         # Logging verbosity (DEBUG, INFO, WARNING, ERROR)
```

### Enabling H.265/1440p Quality (Optional)

Twitch restricts higher quality streams to authenticated users. Without authentication, StreamVault is limited to 1080p H.264.

To enable H.265/1440p:

1. Open Twitch.tv in your browser and log in
2. Press F12 to open Developer Tools
3. Go to Console tab
4. Run this command:
   ```javascript
   document.cookie.split("; ").find(item=>item.startsWith("auth-token="))?.split("=")[1]
   ```
5. Copy the 30-character token (without quotes)
6. Add to `.env`:
   ```env
   TWITCH_OAUTH_TOKEN=abcdefghijklmnopqrstuvwxyz0123
   ```
7. Restart container: `docker compose restart app`

**Without OAuth token**: Limited to 1080p60 H.264  
**With OAuth token**: Access to 1440p60 H.265/HEVC (better quality, smaller files)

See `BROWSER_TOKEN_SETUP.md` for detailed instructions.

### HTTPS Setup Example (Nginx)

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
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

## Documentation

Comprehensive documentation is available in the `docs/` folder:

- **USER_GUIDE.md** - Complete user guide covering setup, configuration, and usage
- **BROWSER_TOKEN_SETUP.md** - Detailed guide for enabling H.265/1440p quality

## Configuration

### Recording Settings

Configure recording behavior in the web interface under Settings > Recording:

- **Output Directory**: Where recordings are saved
- **Filename Template**: Customize file naming with variables
- **Quality**: Choose recording quality (best, 1080p, 720p, etc.)
- **Auto Remux**: Automatically convert TS files to MP4
- **Generate Chapters**: Create chapter files from stream events
- **Create Thumbnails**: Generate video thumbnails
- **Generate Metadata**: Create NFO files for media servers

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

Configure globally or per-streamer for fine-grained control.

### Notification Configuration

StreamVault uses Apprise for notifications, supporting 100+ services:

**Example URLs:**
- Discord: `discord://webhook_id/webhook_token`
- Telegram: `tgram://bot_token/chat_id`
- Ntfy: `ntfy://topic_name`
- Email: `mailtos://user:password@smtp.example.com`

See [Apprise Documentation](https://github.com/caronc/apprise) for complete URL formats.

## API Reference

StreamVault provides a comprehensive REST API for automation:

```bash
# Streamer Management
GET /api/streamers                    # List all streamers
POST /api/streamers                   # Add new streamer
PUT /api/streamers/{id}               # Update streamer settings
DELETE /api/streamers/{id}            # Delete streamer

# Recording Control
POST /api/recording/start/{id}        # Start recording manually
POST /api/recording/stop/{id}         # Stop recording
GET /api/recording/status             # Get recording status

# Video Management
GET /api/videos                       # List all videos
GET /api/videos/stream/{streamer}/{filename}  # Stream video
DELETE /api/videos/{id}               # Delete video

# Background Queue
GET /api/background-queue/stats       # Queue statistics
GET /api/background-queue/active-tasks  # Active tasks
POST /api/background-queue/cancel-stream/{id}  # Cancel stream tasks

# System Administration
GET /api/admin/test/health            # System health check
POST /api/admin/test/recording-workflow  # Test recording workflow
GET /api/admin/test/logs              # Get system logs
```

Interactive API documentation available at: `https://your-domain.com/docs`

## Development

### Local Development Setup

**Backend:**
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd app/frontend
npm install
npm run dev
```

### Project Structure

```
streamvault/
├── app/
│   ├── frontend/          # Vue.js PWA application
│   │   ├── src/
│   │   │   ├── components/   # Vue components
│   │   │   ├── composables/  # Reusable composition functions
│   │   │   ├── views/        # Page components
│   │   │   └── styles/       # SCSS styles
│   │   └── dist/          # Built frontend assets
│   ├── routes/            # FastAPI route handlers
│   ├── services/          # Business logic
│   │   ├── recording/     # Recording service modules
│   │   ├── background_queue_service.py  # Task queue
│   │   ├── metadata_service.py  # Metadata generation
│   │   └── thumbnail_service.py  # Thumbnail generation
│   ├── models/            # Database models
│   ├── schemas/           # Pydantic schemas
│   └── utils/             # Utility functions
├── docs/                  # Documentation
├── migrations/            # Database migrations
├── docker/                # Docker configuration
└── requirements.txt       # Python dependencies
```

### Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Quality

The project uses the following tools for code quality:
- **flake8** - Python linting
- **black** - Code formatting
- **isort** - Import sorting
- **mypy** - Type checking
- **bandit** - Security scanning
- **safety** - Dependency vulnerability checking

## System Requirements

### Minimum Requirements
- **CPU**: 2 cores
- **RAM**: 1GB
- **Storage**: 50GB (recordings grow quickly - plan for 2-8GB per hour per stream)
- **Network**: Stable internet connection

### Recommended Requirements
- **CPU**: 4+ cores
- **RAM**: 2GB
- **Storage**: 1TB+ SSD
- **Network**: High-speed internet for multiple concurrent recordings

**Storage Warning**: Stream recordings can accumulate very quickly. A single 4-hour stream in 1080p can be 8-15GB. Configure cleanup policies early to manage storage.

## Support and Community

- **Issues**: [GitHub Issues](https://github.com/Serph91P/StreamVault/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Serph91P/StreamVault/discussions)
- **Wiki**: [Project Wiki](https://github.com/Serph91P/StreamVault/wiki)

## Background Processing System

StreamVault includes a sophisticated background processing system for post-recording tasks:

**Task Types:**
- Metadata generation from stream information
- Chapter file creation from stream events
- MP4 remuxing from TS source files
- MP4 validation before cleanup
- Thumbnail generation from video content
- Intelligent cleanup after successful validation

**Features:**
- Real-time monitoring in web interface
- Priority system (validation before optional tasks)
- Automatic retry with exponential backoff
- Dependency resolution for correct task ordering
- Graceful shutdown without data loss

## Roadmap

**Completed Features:**
- Background processing system with dependency-based task queue
- Media server integration (Plex, Emby, Jellyfin, Kodi)
- Chapter support with automatic generation from stream events
- Admin test system with comprehensive health checks
- Proxy support with automatic audio sync optimization
- H.265/1440p quality support via browser token authentication

**Planned Features:**
- Cloud storage integration (S3, Google Drive, Dropbox)
- Advanced analytics and recording statistics
- Stream highlight detection and extraction
- Multi-platform support (YouTube, Kick, etc.)
- Mobile apps for iOS and Android

## Acknowledgments

StreamVault is built on top of excellent open-source projects:

- [Streamlink](https://streamlink.github.io/) - Stream recording backbone
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Vue.js](https://vuejs.org/) - Progressive JavaScript framework
- [Twitch API](https://dev.twitch.tv/docs/api/) - Stream data and webhooks
- [FFmpeg](https://ffmpeg.org/) - Video processing
- [MP4Box](https://gpac.wp.imt.fr/mp4box/) - MP4 metadata processing
- [PostgreSQL](https://www.postgresql.org/) - Database system
- [Docker](https://www.docker.com/) - Containerization

## License

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

**StreamVault** - Never miss a stream again.

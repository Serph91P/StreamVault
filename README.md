<div align="center">

# StreamVault

### Self-hosted Twitch stream recorder and media library

Never miss a stream again. StreamVault automatically detects when your favorite streamers go live, records their broadcasts with Streamlink, performs post-processing with rich metadata and artwork, and serves everything through a modern Progressive Web App.

[![Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.5-4FC08D?style=flat-square&logo=vue.js&logoColor=white)](https://vuejs.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

[Features](#features) • [Getting Started](#getting-started) • [Documentation](#documentation) • [API Reference](#api-reference)

![StreamVault Interface](https://via.placeholder.com/800x400/1a1a1a/4FC08D?text=StreamVault+Interface)

</div>

---

## Features

### Automated Recording
- **EventSub webhooks** - Instant stream detection when channels go live
- **Quality selection** - Record in best quality or choose specific resolutions (1080p, 720p, 480p)
- **H.265/AV1 codecs** - Access advanced codecs and 1440p quality with browser token authentication
- **Multi-hour streams** - Safe 24h+ recording with automatic segmentation
- **Proxy support** - HTTP/HTTPS proxies with automatic audio synchronization
- **Manual controls** - Start and stop recordings on-demand via web interface

### Rich Media Library
- **Metadata generation** - Comprehensive NFO files with title, description, date, and categories
- **Automatic chapters** - VTT and XML chapter files from stream events
- **Thumbnails** - Multiple quality options generated from video content
- **Artwork pipeline** - Poster, banner, and fanart images for media servers
- **Episode numbering** - Automatic episode tracking per streamer
- **Media server ready** - Compatible with Plex, Emby, Jellyfin, and Kodi

### Modern Web Interface
- **Progressive Web App** - Install on any device, works offline
- **Real-time updates** - WebSocket connections show live recording status
- **Responsive design** - Touch-optimized for phones and tablets
- **Dark/Light themes** - Automatic system theme detection
- **Background queue monitor** - Track post-processing tasks in real-time
- **Session authentication** - Secure cookie-based authentication

### Intelligent Management
- **Storage policies** - Automatic cleanup by age, size, or file count
- **Per-streamer settings** - Individual recording preferences and cleanup rules
- **Filename templates** - Customize naming with variables (streamer, date, category, title)
- **Bulk operations** - Enable/disable multiple streamers at once
- **Import follows** - Sync your Twitch followed channels

### Notifications
- **100+ services** - Discord, Telegram, Slack, Ntfy, Email, and more via Apprise
- **Web push** - Browser notifications with automatic VAPID key generation
- **Event filtering** - Choose which events trigger notifications
- **Test system** - Verify notification configuration before deploying



---

## Getting Started

### Prerequisites

Before you begin, ensure you have:

- **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)
- **HTTPS domain with valid certificate** - Required for Twitch EventSub webhooks
- **Twitch Developer Application** - Free, [create one here](https://dev.twitch.tv/console/apps)
- **Minimum 2GB RAM** and **50GB storage** (recordings grow 2-8GB per hour at 1080p)

> [!IMPORTANT]
> Twitch EventSub webhooks require a publicly accessible HTTPS endpoint with a valid SSL certificate. Use Let's Encrypt with Traefik, Caddy, Nginx, or a Cloudflare Tunnel.

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Serph91P/StreamVault.git
   cd StreamVault
   ```

2. **Create environment configuration:**
   ```bash
   cp .env.example .env
   ```

3. **Configure Twitch application:**
   
   Create a [Twitch application](https://dev.twitch.tv/console/apps):
   - **Name**: StreamVault (or your preference)
   - **OAuth Redirect URLs**: `https://your-domain.com/auth/callback`
   - **Category**: Application Integration
   
   Copy the Client ID and Client Secret to your `.env` file:
   ```env
   TWITCH_APP_ID=your_client_id_here
   TWITCH_APP_SECRET=your_client_secret_here
   BASE_URL=https://your-domain.com
   EVENTSUB_SECRET=random_secure_string_here
   ```

4. **Start StreamVault:**
   ```bash
   docker compose -f docker/docker-compose.yml up -d
   ```

5. **Access the web interface:**
   
   Open `https://your-domain.com` in your browser (port 7000 is used internally).

### Configuration

#### Environment Variables

Edit your `.env` file with these settings:

```env
# Twitch API Configuration (Required)
TWITCH_APP_ID=your_twitch_client_id
TWITCH_APP_SECRET=your_twitch_client_secret
TWITCH_OAUTH_TOKEN=                    # Optional: enables H.265/1440p

# Application URLs (Required)
BASE_URL=https://your-domain.com       # Must be HTTPS
EVENTSUB_SECRET=random_secure_string   # Generate with: openssl rand -hex 32

# Database Configuration
POSTGRES_USER=streamvault
POSTGRES_PASSWORD=strong_secure_password_here
POSTGRES_DB=streamvault

# Optional Settings
TZ=Europe/Berlin                       # Your timezone
LOG_LEVEL=INFO                         # DEBUG, INFO, WARNING, ERROR
```

#### HTTPS Setup Example

**Using Nginx:**

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

**Using Caddy:**

```caddy
your-domain.com {
    reverse_proxy localhost:7000
}
```

### Enabling Premium Quality

> [!NOTE]
> Twitch restricts third-party apps to 1080p H.264. To unlock H.265/AV1 codecs and 1440p quality, add a browser authentication token.

1. Log in to [Twitch.tv](https://www.twitch.tv)
2. Open browser DevTools (F12) → Console tab
3. Run this command:
   ```javascript
   document.cookie.split("; ").find(item=>item.startsWith("auth-token="))?.split("=")[1]
   ```
4. Copy the 30-character token and add to `.env`:
   ```env
   TWITCH_OAUTH_TOKEN=abc123xyz456def789ghi012jkl345
   ```
5. Restart the container:
   ```bash
   docker compose restart app
   ```

**Quality comparison:**
- **Without token**: 1080p60 H.264 only
- **With token**: Up to 1440p60, H.265/HEVC, AV1, smaller file sizes

See [`docs/BROWSER_TOKEN_SETUP.md`](docs/BROWSER_TOKEN_SETUP.md) for detailed instructions.



---

## Documentation

Comprehensive guides are available in the `docs/` directory:

- **[User Guide](docs/USER_GUIDE.md)** - Complete setup and usage instructions
- **[Browser Token Setup](docs/BROWSER_TOKEN_SETUP.md)** - Enable H.265/1440p quality



---

## Usage

### Adding Streamers

1. Navigate to the **Streamers** page
2. Click **Add Streamer**
3. Enter the Twitch username
4. Configure recording preferences (optional):
   - Recording quality (best, 1080p, 720p, etc.)
   - Filename template
   - Cleanup policies
5. Enable recording for the streamer

### Importing Followed Channels

1. Go to **Settings** → **Twitch Connection**
2. Click **Connect Twitch Account**
3. Authorize StreamVault to access your followed channels
4. Select channels to import
5. Configure default recording settings

### Managing Recordings

**Manual Recording:**
- Click the record button on any streamer card to start recording
- Stop recording anytime from the dashboard or streamer page

**Automatic Recording:**
- Enable "Auto Record" for streamers you want to monitor
- StreamVault detects when they go live via Twitch webhooks
- Recordings start automatically and stop when the stream ends

### Configuring Notifications

1. Go to **Settings** → **Notifications**
2. Add notification service URLs (see [Apprise documentation](https://github.com/caronc/apprise))
3. Select which events trigger notifications:
   - Stream online/offline
   - Recording started/completed/failed
   - Favorite category detected
4. Test your configuration with the **Send Test** button

**Example service URLs:**
```
Discord: discord://webhook_id/webhook_token
Telegram: tgram://bot_token/chat_id
Ntfy: ntfy://topic_name
Email: mailtos://user:password@smtp.example.com
```

### Storage Management

**Global Cleanup Policy:**
1. Go to **Settings** → **Recording**
2. Enable automatic cleanup
3. Set limits:
   - Maximum age (days)
   - Maximum storage (GB)
   - Maximum file count
4. Choose which limit triggers cleanup (first met or all met)

**Per-Streamer Override:**
- Edit any streamer's settings
- Enable custom cleanup policy
- Set streamer-specific limits

> [!WARNING]
> Recordings grow quickly (2-8GB per hour at 1080p). Configure cleanup policies early to prevent storage issues.



---

## API Reference

StreamVault provides a REST API for automation and integration. Interactive documentation is available at `https://your-domain.com/docs`.

### Common Endpoints

```bash
# Streamer Management
GET    /api/streamers              # List all streamers
POST   /api/streamers              # Add new streamer
PUT    /api/streamers/{id}         # Update streamer settings
DELETE /api/streamers/{id}         # Delete streamer

# Recording Control
POST   /api/recording/start/{id}   # Start manual recording
POST   /api/recording/stop/{id}    # Stop recording
GET    /api/recording/status       # Get recording status

# Video Management
GET    /api/videos                 # List all recordings
GET    /api/videos/stream/{streamer}/{filename}  # Stream video
DELETE /api/videos/{id}            # Delete recording

# Background Queue
GET    /api/background-queue/stats            # Queue statistics
GET    /api/background-queue/active-tasks     # Active tasks
POST   /api/background-queue/cancel-stream/{id}  # Cancel tasks

# System Health
GET    /api/admin/test/health                 # Health check
POST   /api/admin/test/recording-workflow     # Test workflow
```

### Authentication

All API requests require session authentication. Use the same session cookie obtained through web interface login.



---

## Development

### Local Development

StreamVault supports local development without Docker:

**Prerequisites:**
- Python 3.12+
- Node.js 20+
- PostgreSQL 15+ (or use SQLite for testing)

**Backend:**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd app/frontend

# Install dependencies
npm install

# Start development server (proxies API requests to backend)
npm run dev
```

**Quick start script:**
```bash
./dev.sh      # Linux/Mac
dev.bat       # Windows
```

### Project Architecture

```
streamvault/
├── app/
│   ├── frontend/              # Vue 3 PWA
│   │   ├── src/
│   │   │   ├── components/   # Reusable components
│   │   │   ├── composables/  # Composition API logic
│   │   │   ├── views/        # Page components
│   │   │   └── styles/       # SCSS design system
│   │   └── dist/             # Built assets
│   ├── routes/               # FastAPI endpoints
│   ├── services/             # Business logic
│   │   ├── recording/        # Recording engine
│   │   ├── background_queue_service.py
│   │   └── metadata_service.py
│   ├── models.py             # SQLAlchemy models
│   ├── schemas/              # Pydantic schemas
│   └── utils/                # Utilities
├── migrations/               # Database migrations
├── docker/                   # Docker configuration
└── tests/                    # Test suites
```

### Technology Stack

**Backend:**
- FastAPI (Python 3.12+)
- SQLAlchemy ORM
- PostgreSQL 15+
- Streamlink for recording
- FFmpeg for video processing

**Frontend:**
- Vue 3.5 with Composition API
- TypeScript 5.6
- Vite build system
- Pinia state management
- SCSS for styling

**Infrastructure:**
- Docker & Docker Compose
- GitHub Actions CI/CD
- AsyncIO task queue

### Running Tests

```bash
# Backend tests
pytest tests/ -v

# Frontend type checking
cd app/frontend
npm run type-check

# Frontend linting
npm run lint
```



---

## System Requirements

### Minimum Specifications
- **CPU**: 2 cores
- **RAM**: 2GB
- **Storage**: 50GB
- **Network**: Stable internet connection

### Recommended Specifications
- **CPU**: 4+ cores
- **RAM**: 4GB
- **Storage**: 1TB+ SSD
- **Network**: High-speed connection for concurrent recordings

> [!WARNING]
> Stream recordings accumulate quickly. A single 4-hour stream at 1080p can be 8-15GB. Plan storage accordingly and configure cleanup policies.

---

## Frequently Asked Questions

<details>
<summary><b>Can I record multiple streams simultaneously?</b></summary>

Yes! StreamVault can record multiple streams at once. Resource usage scales with the number of concurrent recordings. Ensure adequate CPU and RAM for your recording count.
</details>

<details>
<summary><b>What quality options are available?</b></summary>

Without browser token: 160p, 360p, 480p, 720p, 1080p (H.264)
With browser token: All above + 1440p (if available), H.265/HEVC, AV1 codecs

Browser token provides better compression and quality at smaller file sizes.
</details>

<details>
<summary><b>Can I run StreamVault without HTTPS?</b></summary>

No. Twitch EventSub webhooks require valid HTTPS with a trusted SSL certificate. Use Let's Encrypt (free) via Traefik, Caddy, Nginx, or Cloudflare Tunnel.
</details>

<details>
<summary><b>How do I migrate to a new server?</b></summary>

1. Stop the container: `docker compose down`
2. Copy the `recordings/` directory and Docker volumes
3. Transfer `.env` file
4. Start on new server: `docker compose up -d`

Database and metadata are stored in Docker volumes (`app_data`, `app_logs`, `postgres_data`).
</details>

<details>
<summary><b>Can I use this with other platforms like YouTube?</b></summary>

Currently StreamVault only supports Twitch. Multi-platform support is on the roadmap.
</details>

---

## Support

- **Issues & Bugs**: [GitHub Issues](https://github.com/Serph91P/StreamVault/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Serph91P/StreamVault/discussions)

When reporting issues, please include:
- StreamVault version
- Docker/OS version
- Relevant logs from `docker compose logs app`
- Steps to reproduce

---

## Acknowledgments

StreamVault is built with excellent open-source projects:

- [Streamlink](https://streamlink.github.io/) - Stream extraction
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Vue.js](https://vuejs.org/) - Progressive JavaScript framework
- [FFmpeg](https://ffmpeg.org/) - Video processing
- [PostgreSQL](https://www.postgresql.org/) - Database
- [Twitch API](https://dev.twitch.tv/docs/api/) - Stream data and webhooks

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**StreamVault** - Never miss a stream again

[Report Bug](https://github.com/Serph91P/StreamVault/issues) • [Request Feature](https://github.com/Serph91P/StreamVault/discussions)

</div>

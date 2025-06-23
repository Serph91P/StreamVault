# StreamVault 📹

**StreamVault** is a powerful, self-hosted streaming recorder that automatically captures live streams from Twitch and other platforms. Built with FastAPI and Vue.js, it provides a modern web interface for managing streamers, recordings, and viewing your archived content.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.3+-4FC08D.svg)](https://vuejs.org)
[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ Features

### 🎥 Stream Recording
- **Automatic Stream Detection**: Monitor streamers and automatically start recording when they go live
- **High-Quality Recording**: Uses Streamlink for optimal stream capture with customizable quality settings
- **Multi-Platform Support**: Primarily focused on Twitch with extensible architecture for other platforms
- **Proxy Support**: Full HTTP/HTTPS proxy support with audio-sync optimizations (configured via web interface)

### 🎮 Streamer Management
- **Easy Streamer Addition**: Add streamers with simple username input
- **Real-time Status**: Live monitoring of streamer status and recording state
- **Bulk Operations**: Manage multiple streamers efficiently
- **Recording Policies**: Customizable per-streamer recording settings

### 📱 Modern Web Interface
- **Responsive Design**: Beautiful, mobile-friendly interface
- **Progressive Web App (PWA)**: Install as a native app on any device
- **Dark/Light Theme**: Automatic theme switching based on system preferences
- **Real-time Updates**: Live status updates using WebSockets

### 🎬 Video Management
- **Built-in Video Player**: Stream and watch recordings directly in the browser
- **Smart Organization**: Automatic file organization by streamer and date
- **Search & Filter**: Powerful search capabilities across all recordings
- **Metadata Extraction**: Automatic extraction of stream metadata and thumbnails

### 🔧 Advanced Configuration
- **Recording Templates**: Customizable filename templates with variables
- **Quality Selection**: Flexible quality settings (best, worst, specific resolutions)
- **Cleanup Policies**: Automatic cleanup based on age, size, or count
- **Push Notifications**: Push notifications for recording events via Apprise
- **API Access**: Full REST API for automation and integration

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- At least 1GB RAM for the application
- **Significant storage space for recordings** (streams can be 2-8GB per hour depending on quality)
- **Reverse Proxy with Valid SSL Certificate** (for Twitch EventSub webhooks)
  - Nginx, Traefik, or similar
  - Valid SSL certificate (Let's Encrypt recommended)
  - External accessibility required for Twitch webhooks

> **Why is HTTPS required?** Twitch EventSub webhooks require a publicly accessible HTTPS endpoint with a valid SSL certificate. This is a Twitch requirement for security reasons and cannot be bypassed.

#### Alternative Reverse Proxy Solutions:

- **Traefik** with automatic Let's Encrypt certificates
- **Caddy** with automatic HTTPS
- **Cloudflare Tunnel** for easy external access

### 1. Download Required Files

You only need two files to run StreamVault:

```bash
# Download docker-compose.yml
curl -O https://raw.githubusercontent.com/Serph91P/StreamVault/main/docker-compose.yml

# Download .env.example as template
curl -O https://raw.githubusercontent.com/Serph91P/StreamVault/main/.env.example
```

### 2. Environment Setup

Rename `.env.example` to `.env` and configure:

```env
# Twitch API Configuration (Required)
TWITCH_APP_ID=your_twitch_client_id
TWITCH_APP_SECRET=your_twitch_client_secret

# Application Configuration
BASE_URL=https://your-domain.com  # Must be externally accessible with valid SSL
EVENTSUB_SECRET=your_random_secret_here

# Database Configuration
POSTGRES_USER=streamvault
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=streamvault
```

### 3. Get Twitch API Credentials

1. Visit [Twitch Developer Console](https://dev.twitch.tv/console/apps)
2. Click **"Create Application"**
3. Fill in the application details:
   - **Name**: StreamVault (or your preferred name)
   - **OAuth Redirect URLs**: `https://your-domain.com/auth/callback`
   - **Category**: Application Integration
4. Copy the **Client ID** and **Client Secret**
5. Add them to your `.env` file

### 4. Set Up Reverse Proxy

StreamVault requires a reverse proxy with SSL for Twitch EventSub webhooks to work.

#### Example Nginx Configuration:

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

### 5. Start the Application

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app
```

### 6. Access the Application

Open your browser and navigate to `https://your-domain.com`

> **Important**: The application runs on port 7000 internally but should be accessed through your reverse proxy on port 443 (HTTPS).

> **Storage Management**: Recordings can accumulate very quickly. A typical 1080p stream generates 2-4GB per hour. Monitor your storage usage and configure cleanup policies to prevent disk space issues.

## 📖 Documentation

### Database Migrations

StreamVault includes a robust database migration system that handles schema updates automatically:

#### Automatic Migrations

- **On Startup**: Migrations run automatically when the application starts
- **Idempotent**: Safe to run multiple times - won't duplicate existing changes
- **Error Handling**: Graceful handling of migration failures with detailed logging

#### Manual Migration Management

If you need to run migrations manually:

```bash
# Using the shell script (Linux/macOS)
./migrate.sh

# Using PowerShell script (Windows)
.\migrate.ps1

# Using Python directly
python run_safe_migrations.py
```

#### Migration Status

The migration system tracks which migrations have been applied and provides detailed logs:

```
🚀 Starting safe migration process...
✅ Migrations tracking table ready
⏭️  Migration 20250522_add_stream_indices already applied, skipping
🔄 Running migration: Add recording_path column to streams table
✅ Migration 20250609_add_recording_path completed successfully
🎯 Migration summary: 4 successful, 0 failed
```

#### Troubleshooting Migrations

- **Column already exists**: This is normal - the system will skip existing columns
- **Table already exists**: Also normal - idempotent design prevents duplicates
- **Migration tracking**: All migrations are logged in the `applied_migrations` table

### Configuration

#### Recording Settings

StreamVault offers extensive recording configuration options:

- **Output Directory**: Where recordings are stored
- **Filename Template**: Customize file naming with variables like `{streamer}`, `{title}`, `{date}`
- **Quality Settings**: Choose recording quality (best, worst, 1080p, 720p, etc.)
- **Remux to MP4**: Automatically convert recordings to MP4 format

#### Cleanup Policies

Automatic cleanup helps manage storage:

```json
{
  "max_age_days": 30,
  "max_size_gb": 100,
  "max_files": 50,
  "enabled": true
}
```

#### Proxy Configuration

For users requiring proxy support:

- Configure HTTP/HTTPS proxies in settings
- Automatic audio-sync optimizations for proxy connections
- Enhanced buffering and retry logic for stable recordings

### API Reference

StreamVault provides a comprehensive REST API:

```bash
# Get all streamers
GET /api/streamers

# Add a new streamer
POST /api/streamers
{
  "username": "streamername",
  "platform": "twitch"
}

# Start recording manually
POST /api/recording/start/{streamer_id}

# Get all videos
GET /api/videos

# Stream a video
GET /api/videos/stream/{streamer_name}/{filename}
```

Full API documentation is available at `https://your-domain.com/docs` when running the application.

## 🛠️ Development

### Local Development Setup

1. **Backend Development**:
```bash
# Install Python dependencies
pip install -r requirements.txt

# Run database migrations
python -m app.migrations_init

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2. **Frontend Development**:
```bash
cd app/frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Project Structure

```
streamvault/
├── app/
│   ├── frontend/          # Vue.js frontend application
│   ├── routes/           # FastAPI route handlers
│   ├── services/         # Business logic services
│   ├── models/           # Database models
│   ├── schemas/          # Pydantic schemas
│   └── migrations/       # Database migrations
├── docs/                 # Documentation
├── recordings/           # Default recordings directory
├── docker-compose.yml    # Docker configuration
└── requirements.txt      # Python dependencies
```

### Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 🔧 Configuration Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TWITCH_APP_ID` | Twitch application client ID | - | Yes |
| `TWITCH_APP_SECRET` | Twitch application client secret | - | Yes |
| `BASE_URL` | Application base URL (must be HTTPS with valid certificate) | - | Yes |
| `EVENTSUB_SECRET` | Secret for Twitch EventSub webhook validation | Auto-generated | No |
| `POSTGRES_USER` | PostgreSQL username | `streamvault` | Yes |
| `POSTGRES_PASSWORD` | PostgreSQL password | - | Yes |
| `POSTGRES_DB` | PostgreSQL database name | `streamvault` | Yes |

> **Note**: Push notifications (Apprise) are configured through the web interface, not via environment variables.

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

## 📋 Roadmap

- [ ] **Multi-platform Support**: YouTube, Facebook Gaming, etc.
- [ ] **Cloud Storage Integration**: S3, Google Drive, Dropbox
- [ ] **Advanced Analytics**: Recording statistics and insights
- [ ] **Stream Highlights**: Automatic highlight detection and extraction

## 🙏 Acknowledgments

- [Streamlink](https://streamlink.github.io/) - The backbone of our recording functionality
- [FastAPI](https://fastapi.tiangolo.com/) - Modern, fast web framework for APIs
- [Vue.js](https://vuejs.org/) - Progressive JavaScript framework for the frontend
- [Twitch API](https://dev.twitch.tv/docs/api/) - Stream data and webhooks

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

**StreamVault** - Never miss a stream again! 🎮✨

# StreamVault User Guide

This guide covers everything you need to know to set up and use StreamVault effectively.

## Table of Contents

1. [Installation](#installation)
2. [Initial Setup](#initial-setup)
3. [Adding Streamers](#adding-streamers)
4. [Recording Configuration](#recording-configuration)
5. [Notification Setup](#notification-setup)
6. [Video Management](#video-management)
7. [Media Server Integration](#media-server-integration)
8. [Troubleshooting](#troubleshooting)

## Installation

### Prerequisites

- Docker and Docker Compose installed
- A server with at least 2GB RAM and 50GB+ storage
- Public HTTPS domain for Twitch EventSub webhooks
- Twitch Developer Application (instructions below)

### Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/Serph91P/StreamVault.git
   cd StreamVault
   ```

2. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` with your configuration (see Configuration section below)

4. Start the application:
   ```bash
   docker compose -f docker/docker-compose.yml up -d
   ```

5. Access the web interface at `https://your-domain.com`

## Initial Setup

### Creating a Twitch Application

StreamVault requires a Twitch application to access the Twitch API:

1. Go to [Twitch Developer Console](https://dev.twitch.tv/console/apps)
2. Click "Create Application"
3. Fill in the details:
   - **Name**: StreamVault (or your preferred name)
   - **OAuth Redirect URLs**: `https://your-domain.com/auth/callback`
   - **Category**: Application Integration
4. Copy the **Client ID** and generate a **Client Secret**
5. Add these to your `.env` file:
   ```env
   TWITCH_APP_ID=your_client_id_here
   TWITCH_APP_SECRET=your_client_secret_here
   ```

### Environment Configuration

Edit your `.env` file with the following required settings:

```env
# Twitch API Configuration
TWITCH_APP_ID=your_twitch_client_id
TWITCH_APP_SECRET=your_twitch_client_secret
TWITCH_OAUTH_TOKEN=                    # Optional - for H.265/1440p quality

# Application URLs
BASE_URL=https://your-domain.com       # Must be HTTPS with valid certificate
EVENTSUB_SECRET=random_secure_string   # Generate a random string

# Database Configuration
POSTGRES_USER=streamvault
POSTGRES_PASSWORD=strong_secure_password
POSTGRES_DB=streamvault

# Optional Settings
TZ=Europe/Berlin                       # Your timezone
LOG_LEVEL=INFO                         # Logging verbosity (DEBUG, INFO, WARNING, ERROR)
```

### Setting Up HTTPS (Required)

Twitch EventSub webhooks require a valid HTTPS certificate. Choose one of these options:

**Option 1: Nginx Reverse Proxy with Let's Encrypt**

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
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

**Option 2: Cloudflare Tunnel (No Port Forwarding Required)**

1. Install Cloudflare Tunnel on your server
2. Configure tunnel to point to `http://localhost:7000`
3. Cloudflare provides HTTPS automatically

**Option 3: Caddy (Automatic HTTPS)**

```caddy
your-domain.com {
    reverse_proxy localhost:7000
}
```

### Enabling H.265/1440p Quality (Optional)

By default, StreamVault can record up to 1080p60 in H.264. To unlock H.265 codec and 1440p quality:

1. Open Twitch.tv in your browser and log in
2. Press F12 to open Developer Tools
3. Go to the Console tab
4. Run this command:
   ```javascript
   document.cookie.split("; ").find(item=>item.startsWith("auth-token="))?.split("=")[1]
   ```
5. Copy the 30-character token
6. Add it to your `.env` file:
   ```env
   TWITCH_OAUTH_TOKEN=your_30_character_token_here
   ```
7. Restart the container: `docker compose restart app`

**Benefits of Browser Token:**
- H.265/HEVC codec (60% smaller files, same quality)
- Access to 1440p60 quality streams
- Ad-free recordings (with Twitch Turbo subscription)

**Note:** Browser tokens expire after 60-90 days. You'll need to update it when it expires.

## Adding Streamers

### Manual Addition

1. Navigate to the "Streamers" page
2. Click "Add Streamer"
3. Enter the Twitch username (without @ symbol)
4. Configure recording settings:
   - **Auto Record**: Automatically start recording when streamer goes live
   - **Quality**: best, 1080p60, 720p60, etc.
   - **Filename Template**: Customize output filename format

### Bulk Import from Twitch

1. Navigate to the "Streamers" page
2. Click "Import from Twitch"
3. Log in with your Twitch account
4. Select which followed channels to add
5. All selected streamers will be added with default settings

## Recording Configuration

### Global Recording Settings

Configure default recording behavior in Settings > Recording:

**Output Directory**
- Path where recordings are saved
- Default: `/recordings`
- Ensure sufficient disk space (streams can be 2-8GB per hour)

**Filename Template**
- Customize recording filenames using variables:
  - `{streamer}` - Streamer username
  - `{title}` - Stream title
  - `{date}` - Recording date (YYYY-MM-DD)
  - `{time}` - Recording time (HH-MM-SS)
  - `{category}` - Stream category/game
- Example: `{streamer}/{date}/{streamer}_{date}_{time}.ts`

**Quality Settings**
- **best** - Highest available quality
- **1080p60** - 1080p at 60fps
- **720p60** - 720p at 60fps
- **worst** - Lowest quality (bandwidth saving)

**Post-Processing Options**
- **Remux to MP4**: Convert TS files to MP4 after recording
- **Generate Chapters**: Create chapter files from stream events
- **Create Thumbnails**: Generate video thumbnails
- **Generate Metadata**: Create NFO files for media servers

### Per-Streamer Settings

Override global settings for specific streamers:

1. Go to Streamer detail page
2. Click "Edit Settings"
3. Configure custom settings:
   - Recording quality
   - Output directory
   - Filename template
   - Auto-record enabled/disabled
   - Cleanup policies

### Cleanup Policies

Automatically delete old recordings to manage storage:

**Global Cleanup Policy**
- Apply to all streamers without custom policies
- Configure in Settings > Recording

**Per-Streamer Cleanup Policy**
- Override global policy for specific streamers
- Useful for favorites (keep longer) or test channels (delete sooner)

**Cleanup Options:**
- **Max Age**: Delete recordings older than X days
- **Max Size**: Delete oldest recordings when total exceeds X GB
- **Max Files**: Keep only the most recent X recordings
- **Enabled**: Toggle cleanup on/off

Example configuration:
```json
{
  "max_age_days": 30,
  "max_size_gb": 100,
  "max_files": 50,
  "enabled": true
}
```

## Notification Setup

StreamVault supports notifications through Apprise, which works with 100+ services including:
- Discord
- Telegram
- Slack
- Ntfy
- Pushover
- Email (SMTP)
- And many more

### Configuring Notifications

1. Go to Settings > Notifications
2. Enable notifications
3. Add notification URL in Apprise format

**Example URLs:**

Discord:
```
discord://webhook_id/webhook_token
```

Telegram:
```
tgram://bot_token/chat_id
```

Ntfy:
```
ntfy://topic_name
```

Email (SMTP):
```
mailtos://user:password@smtp.example.com
```

See [Apprise Documentation](https://github.com/caronc/apprise) for complete URL format guide.

### Notification Events

Configure which events trigger notifications:

- **Stream Online**: Streamer went live
- **Stream Offline**: Streamer went offline
- **Stream Updated**: Stream title or category changed
- **Favorite Category**: Streamer started streaming a favorite game
- **Recording Started**: Recording successfully started
- **Recording Failed**: Recording encountered an error
- **Recording Completed**: Recording finished successfully

**Recommended Settings:**
- Enable "Recording Failed" to catch issues immediately
- Disable "Recording Started" and "Recording Completed" to avoid notification spam
- Enable "Favorite Category" to get notified about specific games

### Web Push Notifications

Enable browser notifications:

1. Go to Settings > Notifications
2. Click "Enable Browser Notifications"
3. Allow notifications when prompted by browser
4. VAPID keys are automatically generated on first use

Web push works even when browser is closed (requires PWA installation).

## Video Management

### Viewing Recordings

1. Navigate to "Videos" page
2. Browse recordings by:
   - All videos
   - By streamer
   - By date
   - By category

3. Use search and filters to find specific recordings

### Playing Videos

Click on any video thumbnail to open the video player:

**Player Features:**
- Custom touch-optimized controls
- Keyboard shortcuts:
  - Space: Play/Pause
  - F: Fullscreen
  - M: Mute/Unmute
  - Arrow Left/Right: Seek backwards/forwards
- Chapter navigation (if chapters available)
- Quality selection (if multiple qualities available)
- Playback speed control

### Deleting Videos

**Single Video:**
1. Open video details
2. Click "Delete" button
3. Confirm deletion

**Bulk Deletion:**
1. Go to Videos page
2. Select multiple videos
3. Click "Delete Selected"

**Important:** Deletion is permanent and cannot be undone.

### Downloading Videos

Click the download icon on any video to download it to your local device.

## Media Server Integration

StreamVault generates metadata files compatible with popular media servers.

### Plex Integration

1. Configure StreamVault to generate NFO files (Settings > Recording)
2. Set output directory to Plex library location
3. Enable "Generate Metadata" option
4. Plex will automatically detect and index recordings

**Folder Structure:**
```
recordings/
├── StreamerName/
│   ├── 202501/           # YYYYMM season format
│   │   ├── stream_01.mp4
│   │   ├── stream_01.nfo
│   │   ├── stream_01-poster.jpg
│   │   └── stream_01-fanart.jpg
```

### Emby/Jellyfin Integration

Same as Plex - both support NFO metadata format.

### Kodi Integration

Enable NFO generation and ensure proper folder structure. Kodi will read metadata from NFO files.

### Metadata Files Generated

- **NFO files**: XML metadata with stream info, chapters, artwork paths
- **Poster images**: Vertical artwork (streamer profile or category)
- **Fanart images**: Horizontal background artwork
- **Chapter files**: VTT or XML chapter markers

## Troubleshooting

### Common Issues

**Problem: Recordings not starting automatically**

Solutions:
1. Check EventSub webhook status in Settings > System
2. Verify BASE_URL is HTTPS with valid certificate
3. Check Twitch Application OAuth redirect URL matches BASE_URL
4. Ensure EVENTSUB_SECRET is set in environment

**Problem: Poor video quality or buffering**

Solutions:
1. Check internet connection speed
2. Try lower quality setting (720p instead of 1080p)
3. Configure proxy if streaming issues persist
4. Check server CPU/RAM usage during recording

**Problem: Storage filling up quickly**

Solutions:
1. Enable cleanup policies (Settings > Recording)
2. Set max age for recordings (e.g., 30 days)
3. Lower recording quality to reduce file sizes
4. Enable H.265 codec (60% smaller files than H.264)

**Problem: Recording fails immediately**

Solutions:
1. Check logs: `docker logs streamvault`
2. Verify Twitch OAuth token is valid
3. Test network connectivity to Twitch
4. Check disk space availability
5. Verify Streamlink is properly installed

**Problem: Can't log in to web interface**

Solutions:
1. Clear browser cache and cookies
2. Try incognito/private browsing mode
3. Check database is running: `docker ps`
4. Restart application: `docker compose restart app`

### Viewing Logs

**Docker logs:**
```bash
docker logs streamvault -f
```

**Application logs:**
```bash
docker exec streamvault cat /app/logs/app.log
```

**Database logs:**
```bash
docker logs streamvault_db
```

### Getting Help

If you encounter issues not covered in this guide:

1. Check [GitHub Issues](https://github.com/Serph91P/StreamVault/issues) for similar problems
2. Open a new issue with:
   - Clear description of the problem
   - Steps to reproduce
   - Relevant log excerpts
   - Your environment (OS, Docker version, etc.)
3. Join discussions in [GitHub Discussions](https://github.com/Serph91P/StreamVault/discussions)

## Advanced Topics

### Proxy Configuration

If you experience connection issues with Twitch, configure a proxy:

1. Go to Settings > Proxy
2. Add proxy URL (HTTP/HTTPS supported)
3. Test proxy connection
4. Enable proxy for recordings

StreamVault includes automatic audio-sync optimization for proxy connections.

### API Access

StreamVault provides a REST API for automation:

**Documentation:** `https://your-domain.com/docs`

**Example API Calls:**

List streamers:
```bash
curl https://your-domain.com/api/streamers
```

Start recording manually:
```bash
curl -X POST https://your-domain.com/api/recording/start/123
```

Get recording status:
```bash
curl https://your-domain.com/api/recording/status
```

See API documentation for complete endpoint reference.

### Background Processing

StreamVault uses a background task queue for post-processing:

**Task Types:**
- Metadata generation
- Chapter creation
- MP4 remuxing
- Thumbnail generation
- File validation
- Cleanup operations

**Monitoring:**
- View queue status in Settings > System
- See active tasks and completion status
- Retry failed tasks manually
- Cancel long-running tasks if needed

### Database Backups

Backup your database regularly to prevent data loss:

```bash
# Backup database
docker exec streamvault_db pg_dump -U streamvault streamvault > backup.sql

# Restore database
docker exec -i streamvault_db psql -U streamvault streamvault < backup.sql
```

Store backups securely off-site.

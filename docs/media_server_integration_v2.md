# Media Server Integration Guide

## Overview
StreamVault has been refactored for compatibility with media server containers (Plex, Jellyfin, Emby). The new architecture uses relative paths and a simplified directory structure.

## New Directory Structure

```
/recordings/ (or your mount point)
├── StreamerName/
│   ├── tvshow.nfo          # Show metadata
│   ├── 2024/
│   │   └── 01/
│   │       ├── recording.mp4
│   │       ├── recording.nfo      # Episode metadata with relative paths
│   │       └── recording-thumb.jpg # Episode thumbnail
│   └── season.nfo          # Season metadata
└── .media/  # Hidden directory (prevents media servers from creating seasons)
    ├── artwork/
    │   └── StreamerName/
    │       ├── poster.jpg      # Streamer artwork
    │       ├── banner.jpg      # Banner image  
    │       └── fanart.jpg      # Background image
    ├── profiles/
    │   └── streamer_123.jpg    # Profile images
    └── categories/
        └── category_456.jpg    # Category icons
```

## Benefits of the New System

### 1. Hidden .media Directory
- Artwork stored in `.media/artwork/StreamerName/`
- Hidden from media servers (prevents unwanted season creation)
- Organized structure for different image types
- Emby/Jellyfin won't create seasons from image folders

### 2. Relative Paths in NFO Files
```xml
<!-- Before (problematic) -->
<thumb>/recordings/.artwork/CohhCarnage/poster.jpg</thumb>

<!-- After (compatible) -->
<thumb>.media/artwork/CohhCarnage/poster.jpg</thumb>
```

### 3. Automatic Migration
- Application automatically checks for old directory structures on startup
- Migrates images from `.images/` and `.artwork/` to new `.media/` structure
- Removes duplicates and cleans up old directories
- No manual intervention required

## Docker Configuration

### Standard StreamVault Setup
```yaml
version: '3.8'
services:
  streamvault:
    image: frequency2098/streamvault
    volumes:
      - ./recordings:/recordings  # Single volume for everything
    environment:
      - RECORDINGS_DIR=/recordings
```

### With Media Server (Example: Plex)
```yaml
version: '3.8'
services:
  streamvault:
    image: frequency2098/streamvault
    volumes:
      - recordings:/recordings
    
  plex:
    image: plexinc/pms-docker
    volumes:
      - recordings:/data/media  # Same data, different path

volumes:
  recordings:
    driver: local
```

## Migration from Old System

### 1. Automatic Migration on Startup
The application automatically handles migration when it starts:
- Checks for old `.images/` and `.artwork/` directories
- Moves images to new `.media/` structure if needed
- Removes duplicates (keeps newer files)
- Cleans up empty old directories
- Logs migration progress and statistics

### 2. Manual Migration (Optional)
```bash
# Check if migration is needed
curl http://localhost:7000/api/migration/images/status

# Force run migration manually  
curl -X POST http://localhost:7000/api/migration/images
```

### 3. Directory Changes
```bash
# Before
/recordings/
├── StreamerName/
├── .images/
│   ├── profiles/
│   └── artwork/
└── .artwork/

# After  
/recordings/
├── StreamerName/
└── .media/
    ├── artwork/
    │   └── StreamerName/
    │       ├── poster.jpg
    │       ├── banner.jpg
    │       └── fanart.jpg
    ├── profiles/
    └── categories/
```

## Media Server Setup

### Plex
1. Add library as "TV Shows" 
2. Set path to your recordings mount
3. Enable "Local Media Assets" agent
4. Plex will read NFO files and display artwork

### Jellyfin  
1. Add library as "Shows"
2. Set path to your recordings mount
3. Enable "NFO metadata reader"
4. Jellyfin will use NFO files and artwork

### Emby
1. Add library as "TV"
2. Set path to your recordings mount  
3. Enable "NFO metadata reader"
4. Emby will process NFO files and artwork

## Troubleshooting

### Artwork Not Displaying
- Check if `poster.jpg`, `banner.jpg`, `fanart.jpg` exist in streamer directory
- Verify NFO files contain relative paths (not absolute)
- Force refresh library in media server

### Path Issues
- Use `docker exec` to inspect container:
  ```bash
  docker exec -it streamvault ls -la /recordings/StreamerName/
  docker exec -it plex ls -la /data/media/StreamerName/
  ```

### Migration Problems
- Check migration status: `GET /api/migration/images/status`
- Review logs for migration errors
- Manually verify old directories are cleaned up

## Technical Details

### Changed Services
- `metadata_service.py`: Generates relative paths in NFO files
- `image_migration_service.py`: Handles migration from old structure
- Migration API: `/api/migration/images` endpoints

### New Features
- Automatic relative path generation
- Simplified directory structure
- Migration service for old installations
- Direct artwork placement in streamer directories

This architecture makes StreamVault much more flexible for Docker deployments with various media servers!

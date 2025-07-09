# Artwork and Metadata Directory Separation

This document describes the implementation of separated artwork and metadata directories to prevent Emby/Plex from misinterpreting the recordings directory structure.

## Problem Description

Previously, artwork files (banner.jpg, poster.jpg, fanart.jpg, etc.) and metadata files (tvshow.nfo, season.nfo) were created in the `/recordings` directory alongside streamer folders. This caused issues with media servers like Emby and Plex, which would interpret these files as additional "series" or media content.

## Solution

The solution separates artwork and metadata files from the recordings directory by:

1. **Dedicated Artwork Directory**: Created `/app/artwork` for all artwork and metadata files
2. **Docker Volume Mount**: Added a new volume mount in docker-compose.yml
3. **Artwork Service**: New service to manage artwork and metadata separately
4. **Updated References**: All NFO files now reference the separated artwork directory

## Directory Structure

### Before (Problematic)
```
/recordings/
├── teststreamer/                   # Streamer folder (correct)
│   ├── Season 2025-01/            # Season folder (correct)
│   │   └── episode.mp4            # Recording (correct)
│   ├── poster.jpg                 # PROBLEM: Confuses media servers
│   ├── banner.jpg                 # PROBLEM: Confuses media servers
│   ├── tvshow.nfo                 # PROBLEM: Confuses media servers
│   └── actors/                    # PROBLEM: Confuses media servers
└── banner.jpg                     # PROBLEM: Root level artwork
```

### After (Clean)
```
/recordings/
└── teststreamer/                   # Only streamer folders
    └── Season 2025-01/            # Only season folders
        └── episode.mp4            # Only recording files

/app/artwork/
└── teststreamer/                   # Artwork for each streamer
    ├── poster.jpg                 # All artwork files
    ├── banner.jpg
    ├── fanart.jpg
    ├── logo.jpg
    ├── clearlogo.jpg
    ├── season.jpg
    ├── season-poster.jpg
    ├── folder.jpg
    ├── show.jpg
    └── metadata/                  # Metadata files
        ├── tvshow.nfo
        └── Season_2025-01/
            └── season.nfo
```

## Implementation Details

### 1. Docker Configuration

Added new volume mount in `docker-compose.yml`:

```yaml
services:
  app:
    volumes:
      - app_data:/app/data
      - ./recordings:/recordings
      - ./logs:/app/logs
      - ./artwork:/app/artwork  # NEW: Artwork directory
```

### 2. Settings Configuration

Added new setting in `app/config/settings.py`:

```python
class Settings(BaseSettings):
    # Artwork and metadata directory (separate from recordings)
    ARTWORK_BASE_PATH: str = "/app/artwork"
```

### 3. Artwork Service

Created `app/services/artwork_service.py` with the following responsibilities:

- **Artwork Management**: Downloads and saves all artwork formats
- **Metadata Creation**: Creates tvshow.nfo and season.nfo files
- **Directory Organization**: Maintains clean directory structure
- **Path Resolution**: Provides paths for artwork and metadata files

Key methods:
- `save_streamer_artwork()`: Downloads all artwork formats
- `save_streamer_metadata()`: Creates NFO files
- `get_streamer_artwork_dir()`: Returns artwork directory path
- `get_streamer_metadata_dir()`: Returns metadata directory path

### 4. Updated Services

#### MetadataService
- **Removed**: `_save_streamer_images()` function
- **Updated**: NFO files now reference artwork service paths
- **Added**: Integration with artwork service

#### MediaServerStructureService
- **Removed**: `_organize_images()` and `_download_streamer_poster()` functions
- **Updated**: No longer creates artwork files in recordings directory
- **Simplified**: Focuses only on recording file organization

## Benefits

1. **Clean Recordings Directory**: Only contains streamer folders and recordings
2. **Media Server Compatibility**: Emby/Plex no longer see extra "series"
3. **Centralized Artwork**: All artwork managed in one location
4. **Maintainable**: Clear separation of concerns
5. **Scalable**: Easy to add new artwork formats or metadata

## Migration

For existing installations, the artwork files will be created in the new directory on the next stream recording. Existing artwork files in the recordings directory can be manually removed without affecting functionality.

## Implementation Status

✅ **COMPLETED:**
- Docker Compose volume mount configured
- Artwork service created and tested
- MetadataService updated to use artwork service
- MediaServerStructureService updated 
- Settings configuration added
- Test scripts created and verified
- Documentation completed

🧪 **TESTED:**
- Directory structure creation ✅
- Docker volume mount ✅ 
- Recordings directory cleanliness ✅
- Metadata file creation ✅

⚠️ **REQUIRES TESTING WITH REAL STREAM:**
- Full artwork download and save
- Episode NFO creation with artwork references
- Emby/Plex integration verification

## Troubleshooting

### Artwork Directory Not Created
- Check Docker volume mount is properly configured
- Verify container has write permissions to `./artwork`

### NFO Files Reference Wrong Paths
- Check `ARTWORK_BASE_PATH` setting
- Verify artwork service is properly initialized

### Media Server Still Shows Extra Content
- Clear media server cache/metadata
- Rescan library after cleanup
- Remove old artwork files from recordings directory

## Future Enhancements

1. **Migration Script**: Automatic migration of existing artwork
2. **Artwork Cleanup**: Remove orphaned artwork files
3. **Format Options**: Configurable artwork formats per media server
4. **Backup Integration**: Include artwork in backup strategies

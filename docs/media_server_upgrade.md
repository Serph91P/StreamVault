# Media Server Integration Upgrade Guide

## 🚀 Overview

StreamVault now includes enhanced media server integration with optimized directory structures for Plex, Emby, Jellyfin, and Kodi.

## 📁 New Directory Structure

### Before:
```
/recordings/
├── StreamerName/
│   ├── StreamerName_2025-01-15_20-30_Stream Title_Game.mp4
│   ├── StreamerName_2025-01-16_21-45_Another Stream_Game.mp4
│   └── ...
```

### After:
```
/recordings/
├── StreamerName/
│   ├── poster.jpg                    # Show poster
│   ├── folder.jpg                    # Emby/Jellyfin compatibility
│   ├── tvshow.nfo                    # Series metadata
│   ├── Season 2025-01/               # Year-Month seasons
│   │   ├── poster.jpg                # Season poster
│   │   ├── season.nfo                # Season metadata
│   │   ├── StreamerName - S202501E01 - Stream Title.mp4
│   │   ├── StreamerName - S202501E01 - Stream Title.nfo
│   │   ├── StreamerName - S202501E01 - Stream Title-thumb.jpg
│   │   ├── StreamerName - S202501E01 - Stream Title.chapters.vtt
│   │   └── StreamerName - S202501E01 - Stream Title.chapters.xml
│   └── Season 2025-02/
│       └── ...
```

## 🔧 Changes Made

### 1. New Service: `MediaServerStructureService`
- Handles media server optimized file organization
- Creates NFO files with correct image references
- Generates chapter files in multiple formats
- Downloads and organizes thumbnails and posters

### 2. Updated `RecordingService`
- Integrated `MediaServerStructureService`
- Modified `_delayed_metadata_generation` to create optimized structure
- Added `_update_recording_path` helper method
- Enhanced cleanup to close all services

### 3. Updated Templates
- New filename templates for media servers
- Consistent formatting with zero-padded numbers
- Support for Season/Episode naming convention

### 4. Enhanced Documentation
- Complete setup guides for each media server
- Troubleshooting section
- Performance and compatibility notes

## 🎯 Features

### Automatic File Organization:
- ✅ Moves files to media server optimized structure
- ✅ Creates all required metadata files (NFO, chapters)
- ✅ Downloads and organizes images in multiple formats
- ✅ Updates database paths after file moves

### Media Server Compatibility:
- ✅ **Plex**: Standard TV Show structure with NFO support
- ✅ **Emby**: NFO files with local images
- ✅ **Jellyfin**: Chapter files and metadata support
- ✅ **Kodi**: Local information and images

### Image Management:
- ✅ Streamer profile images as show posters
- ✅ Episode thumbnails from Twitch or video extraction
- ✅ Multiple image formats (poster.jpg, folder.jpg)
- ✅ Season-specific posters

### Chapter Support:
- ✅ WebVTT chapters (.chapters.vtt)
- ✅ XML chapters for Emby/Jellyfin (.chapters.xml)
- ✅ Based on actual stream events (category changes, etc.)

## ⚙️ Configuration

### In StreamVault Settings:
1. Go to Recording Settings
2. Select filename template:
   - **For Plex/Emby/Jellyfin**: Use "plex", "emby", or "jellyfin" preset
   - **For chronological**: Use "chronological" preset

### Media Server Setup:
See the complete [Media Server Integration Guide](media_server_integration.md) for detailed setup instructions.

## 🔄 Migration

### Existing Recordings:
- Old recordings will remain in their current structure
- New recordings will use the optimized structure
- You can manually organize old recordings using the same pattern

### Database Updates:
- `recording_path` field will be updated to reflect new file locations
- Stream metadata remains unchanged
- No database migration required

## 🛠️ Troubleshooting

### Files not appearing in media server:
1. Ensure NFO support is enabled in your media server
2. Check that local media assets are enabled
3. Refresh/scan your media library

### Images not loading:
1. Verify `poster.jpg` exists in streamer directory
2. Check that `folder.jpg` is created for Emby/Jellyfin
3. Ensure media server has permission to read image files

### Chapters not working:
1. Check if `.chapters.vtt` or `.chapters.xml` files exist
2. Verify stream events were recorded during the stream
3. Test chapter files manually with VLC

## 📊 Performance Impact

### File Operations:
- Minimal performance impact during recording
- Structure creation happens after recording completion
- Concurrent operations for multiple streamers

### Storage:
- Small increase due to multiple image formats
- NFO files are typically < 1KB each
- Chapter files are usually < 5KB each

## 🎯 Future Enhancements

### Planned Features:
- [ ] Batch migration tool for existing recordings
- [ ] Custom poster/thumbnail upload support
- [ ] Advanced chapter editing interface
- [ ] Multiple media server configurations

### Feedback:
Please report any issues or suggestions for the media server integration feature.

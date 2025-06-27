# Media Server Integration Guide

StreamVault automatically creates an optimized directory structure for media servers like Plex, Emby, Jellyfin, and Kodi.

## 📁 Directory Structure

### Optimized Structure (from `/recordings`):

```
/recordings/
├── StreamerName/
│   ├── poster.jpg                    # Streamer profile image (Show Poster)
│   ├── folder.jpg                    # For Emby/Jellyfin compatibility
│   ├── banner.jpg                    # Banner image
│   ├── fanart.jpg                    # Background fanart
│   ├── tvshow.nfo                    # Series metadata
│   ├── season.nfo                    # Season metadata (when using season structure)
│   ├── actors/
│   │   └── StreamerName.jpg          # Actor/Streamer image
│   ├── Season 2025-01/               # Year-Month season format (zero-padded)
│   │   ├── poster.jpg                # Season poster
│   │   ├── StreamerName - S202501E01 - Stream Title.mp4
│   │   ├── StreamerName - S202501E01 - Stream Title.nfo
│   │   ├── StreamerName - S202501E01 - Stream Title-thumb.jpg
│   │   ├── StreamerName - S202501E01 - Stream Title.chapters.vtt
│   │   └── StreamerName - S202501E01 - Stream Title.chapters.xml
│   └── Season 2025-02/
│       └── ...
```

## 🎯 Media Server Setup

### Plex Setup
1. Add new library → TV Shows
2. Add folder: `/recordings` (in Docker container)
3. Agent: Select "Plex TV Series"
4. Language: English (or preferred language)
5. ✅ Enable "Use local media assets"

### Emby Setup
1. New Media Library → TV Shows
2. Folder path: `/recordings`
3. ✅ Enable "Use NFO files as metadata source"
4. ✅ Enable "Use local images"

### Jellyfin Setup
1. Libraries → Add Media Library → Shows
2. Folder: `/recordings`
3. Metadata downloaders: Enable "Nfo"
4. ✅ Enable "Prefer NFO files"

### Kodi Setup
1. Videos → Files → Add videos
2. Add source: Path to `/recordings`
3. Content type: "TV shows"
4. ✅ Enable "Use local information"

## 🖼️ Image Types

### Automatically generated images:
- **poster.jpg**: Streamer profile image as show poster
- **folder.jpg**: Copy for Emby/Jellyfin compatibility
- **banner.jpg**: Banner format of streamer image
- **fanart.jpg**: Background fanart from streamer image
- **season.jpg**: Season-specific image
- **actors/StreamerName.jpg**: Actor/Streamer image for cast info
- **episode-thumb.jpg**: Episode thumbnail (extracted from stream or Twitch thumbnail)

### Image sources:
1. **Primary**: Twitch stream thumbnail
2. **Fallback**: Video frame extraction (5th minute)
3. **Streamer image**: Twitch profile image

## 📄 Metadata Files

### NFO Files:
- **tvshow.nfo**: Series-level metadata (contains show info, streamer details, genres)
- **season.nfo**: Season metadata (when using season structure)
- **episode.nfo**: Episode-specific metadata (stream title, description, thumbnail references)

**Important**: NFO files use relative paths for images (e.g., `poster.jpg`, `../actors/StreamerName.jpg`) to ensure compatibility across different media server setups.

### Chapter Files:
- **.chapters.vtt**: WebVTT format (for web players)
- **.chapters.xml**: XML format (for Emby/Jellyfin)
- **.chapters.srt**: SRT format (for players with SRT support)

## ⚙️ Configuration

### Filename Templates:
Choose the appropriate template in recording settings:

- **Plex/Emby/Jellyfin**: `{streamer}/Season {year}-{month:02d}/{streamer} - S{year}{month:02d}E{episode:02d} - {title}`
- **Chronological**: `{year}/{month:02d}/{day:02d}/{streamer} - E{episode:02d} - {title} - {hour:02d}-{minute:02d}`
- **Default**: `{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}`

**Note**: All templates use zero-padded numbers (e.g., `01`, `02`) for proper sorting in media servers.

### Docker Volume Setup:
```yaml
volumes:
  - ./recordings:/recordings  # Host → Container
```

## 🔄 Automatic Workflow

1. **Stream is recorded** → Creates TS file
2. **Stream ends** → Conversion to MP4
3. **Metadata generation**:
   - Stream events to chapters
   - Create NFO files
   - Download/extract thumbnails
4. **Structure optimization**:
   - Move file to correct directory structure
   - Create images in all required formats
   - Place metadata files in correct locations

## 🛠️ Troubleshooting

### Media server doesn't recognize content:
1. Check if NFO support is enabled
2. Verify folder permissions (ensure media server can read `/recordings`)
3. Run a library refresh/rescan
4. Verify the correct naming convention is used

### Images not displayed:
1. Check if `poster.jpg` and `folder.jpg` exist in streamer directory
2. Ensure "Use local media" is enabled in media server settings
3. Clear media server cache and restart
4. Verify image files are not corrupted (should be > 1KB)

### Chapters not working:
1. Verify that `.chapters.vtt` or `.chapters.xml` exist alongside video file
2. Ensure stream events were recorded during the stream
3. Manual test with VLC player to verify chapter file format
4. Check if media server supports chapter files

### Episode numbering issues:
1. Episodes are numbered sequentially per month (resets each month)
2. If episodes appear out of order, check file modification dates
3. For manual fixes, rename files following the pattern: `StreamerName - S{YYYYMM}E{NN} - Title`

### Path and permission issues:
1. Ensure Docker volume mapping is correct: `./recordings:/recordings`
2. Check that files are being created with proper permissions
3. Verify no special characters in streamer names that could break paths
4. Use absolute paths in Docker environment variables

## 📊 Season Logic

### Automatic season creation:
- **Season = Year-Month**: `Season 2025-01`, `Season 2025-02`, etc.
- **Episode numbering**: Sequential per month (E01, E02, E03...)
- **Season reset**: Each month starts with episode 1

### Example timeline:
```
January 2025: Season 2025-01
├── E01 (1st stream in January)
├── E02 (2nd stream in January)
└── E03 (3rd stream in January)

February 2025: Season 2025-02
├── E01 (1st stream in February)
└── E02 (2nd stream in February)
```

## ✅ Validation and Testing

### File Structure Validation:
After recording a stream, verify the following structure exists:

```bash
# Example for streamer "TestStreamer" in January 2025
/recordings/TestStreamer/
├── poster.jpg                  # Should exist and be > 1KB
├── folder.jpg                  # Copy of poster.jpg
├── tvshow.nfo                  # XML file with series metadata
├── actors/
│   └── TestStreamer.jpg        # Streamer profile image
└── Season 2025-01/
    ├── poster.jpg              # Season poster
    ├── season.nfo              # Season metadata (if in season structure)
    ├── TestStreamer - S202501E01 - Stream Title.mp4
    ├── TestStreamer - S202501E01 - Stream Title.nfo  # Episode metadata
    ├── TestStreamer - S202501E01 - Stream Title-thumb.jpg
    └── TestStreamer - S202501E01 - Stream Title.chapters.vtt
```

### NFO File Validation:
1. **tvshow.nfo**: Should contain `<tvshow>` root element with streamer info
2. **episode.nfo**: Should contain `<episodedetails>` with correct season/episode numbers
3. **Image references**: Should use relative paths (e.g., `poster.jpg`, not absolute paths)

### Testing with Media Servers:
1. **Plex**: Add library, scan, check if show appears with correct metadata
2. **Jellyfin**: Import library, verify images and episode ordering
3. **Emby**: Add collection, ensure NFO files are read correctly
4. **Kodi**: Add video source, scrape library, test chapter navigation

## 🎯 Optimizations

### Performance:
- Images are downloaded once and copied
- NFO files use streaming metadata
- Chapters based on actual stream events

### Compatibility:
- All common media servers supported
- Standard-compliant NFO structure
- Multiple image formats for maximum compatibility

### Maintenance:
- Automatic cleanup of temporary files
- Logging of all structure creation operations
- Error handling with fallback options
- Consistent episode numbering across months
- Relative path usage in all metadata files for portability

## 🔧 Best Practices

### For Administrators:
1. **Regular Backups**: Backup the `/recordings` directory and database regularly
2. **Storage Management**: Monitor disk space and set up cleanup policies
3. **Permission Verification**: Ensure media server can read all files (755 for directories, 644 for files)
4. **Version Control**: Keep track of configuration changes in recording settings

### For Media Server Setup:
1. **Library Organization**: Use separate libraries for different streamers if needed
2. **Metadata Priority**: Set NFO files as highest priority metadata source
3. **Image Caching**: Allow sufficient cache space for artwork
4. **Scanning Schedule**: Set up automatic library scans for new content

### For Troubleshooting:
1. **Log Analysis**: Check StreamVault logs for file creation and metadata generation
2. **File Validation**: Verify file sizes, permissions, and structure after recording
3. **Test Environment**: Set up a test media server configuration for validation
4. **Backup Strategy**: Keep original recordings in case of metadata regeneration needs

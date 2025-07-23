# Unified Image Service

The Unified Image Service provides centralized image management for StreamVault, handling profile pictures, category images, and stream artwork.

## Features

- **Centralized Storage**: All images stored in `/recordings/.images/` for media server access
- **Automatic Caching**: Images are downloaded and cached locally
- **Fallback URLs**: Graceful fallback to original URLs if cached images unavailable
- **Media Server Integration**: Hidden directory structure won't interfere with media servers
- **Docker Compatible**: Works with Docker volume mounts

## Directory Structure

```
/recordings/.images/
├── profiles/          # Streamer profile images
│   ├── profile_avatar_123.jpg
│   └── profile_avatar_456.jpg
├── categories/        # Category/game images
│   ├── just_chatting.jpg
│   └── league_of_legends.jpg
└── artwork/          # Stream artwork/thumbnails
    ├── profile_avatar_123/
    │   ├── stream_789.jpg
    │   └── stream_790.jpg
    └── profile_avatar_456/
        └── stream_791.jpg
```

## API Endpoints

### Image Serving
- `GET /data/images/profiles/{filename}` - Serve profile images
- `GET /data/images/categories/{filename}` - Serve category images
- `GET /data/images/artwork/{streamer_id}/{filename}` - Serve artwork

### Management API
- `GET /api/images/stats` - Get image cache statistics
- `GET /api/images/streamer/{streamer_id}` - Get streamer image info
- `POST /api/images/streamer/{streamer_id}/download` - Download streamer image
- `GET /api/images/category/{category_name}` - Get category image info
- `POST /api/images/category/{category_name}/download` - Download category image
- `POST /api/images/sync` - Sync all images
- `POST /api/images/cleanup` - Clean up orphaned images

## Usage

### Frontend Integration

The service is automatically integrated into the streamers API. Profile images now use cached versions:

```javascript
// Before: Uses remote Twitch URLs
{
  "profile_image_url": "https://static-cdn.jtvnw.net/jtv_user_pictures/..."
}

// After: Uses cached local URLs with fallback
{
  "profile_image_url": "/data/images/profiles/profile_avatar_123.jpg"
}
```

### Background Sync

The service includes an automatic image sync service that:
- Downloads images when streamers/categories are added
- Runs in the background without blocking the main application
- Retries failed downloads
- Maintains cache consistency

### Manual Operations

```bash
# Sync all profile images
curl -X POST http://localhost:8000/api/images/sync

# Download specific streamer image
curl -X POST http://localhost:8000/api/images/streamer/123/download

# Get statistics
curl http://localhost:8000/api/images/stats
```

## Configuration

The service uses the same recordings directory as configured in the database settings. Images are stored in a hidden `.images` subdirectory to avoid conflicts with media servers.

## Media Server Integration

### Directory Structure
The `.images` directory is hidden and won't be detected as media by most media servers, while still being accessible via the same volume mount.

### Metadata Integration
Images can be referenced in NFO files using relative paths:
```xml
<thumb>/recordings/.images/profiles/profile_avatar_123.jpg</thumb>
```

## Performance

- **Lazy Loading**: Service initializes only when first accessed
- **Caching**: In-memory cache for fast URL lookups
- **Background Processing**: Downloads don't block API requests
- **Fallback**: Graceful degradation if cache unavailable

## Error Handling

- **Missing Dependencies**: Graceful fallback if aiofiles/psutil unavailable
- **Database Errors**: Uses fallback directory if config fails
- **Download Failures**: Tracked and retried automatically
- **File System Issues**: Comprehensive error logging

## Migration from Existing Services

The service replaces and consolidates:
- `artwork_service.py` - Stream artwork management
- `category_image_service.py` - Category image caching

All existing functionality is preserved while adding unified management and better media server integration.

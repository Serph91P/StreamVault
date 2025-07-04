# Streamlink Command Construction in StreamVault

StreamVault uses a modular approach to construct Streamlink commands for capturing live streams, VODs, and clips from Twitch. This approach was inspired by the LiveStreamDVR (lsdvr) TypeScript implementation and provides maximum reliability and flexibility.

## Utility Module

The `app/utils/streamlink_utils.py` module provides the following key functions:

- `get_streamlink_command()`: Creates a command for live stream recording
- `get_streamlink_vod_command()`: Creates a command for VOD downloading
- `get_streamlink_clip_command()`: Creates a command for clip downloading
- `get_proxy_settings_from_db()`: Retrieves proxy settings from the database

## Usage Example

```python
from app.utils.streamlink_utils import get_streamlink_command, get_proxy_settings_from_db

# Get proxy settings from database
proxy_settings = get_proxy_settings_from_db()

# Generate a streamlink command
cmd = get_streamlink_command(
    streamer_name="example_streamer",
    quality="best",
    output_path="/path/to/output.mp4",
    proxy_settings=proxy_settings,
    force_mode=False
)

# Use the command with subprocess
process = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
)
```

## Key Features

- **Modular Design**: Each command-building function is modular and can be reused across the application
- **Proxy Support**: Seamless integration of HTTP and HTTPS proxies with optimized settings
- **Force Mode**: Additional options for difficult connections or manual recording attempts
- **Robust Parameters**: Carefully tuned parameters for maximum stability and recording quality
- **Proper Error Handling**: Validates proxy URLs and other settings before use

## Testing

The streamlink utilities include comprehensive tests in `tests/utils/test_streamlink_utils.py`.

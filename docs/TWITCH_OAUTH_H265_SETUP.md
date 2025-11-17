# Twitch OAuth Token Setup for H.265/1440p Streams

## Overview

Twitch restricts higher quality streams (1440p, H.265/HEVC codec) to **authenticated users only**. Without authentication, StreamVault can only record up to **1080p60 H.264**.

This guide explains how to enable authenticated Twitch access to unlock:
- ✅ **1440p resolution** (2560x1440)
- ✅ **H.265/HEVC codec** (better quality, smaller file sizes)
- ✅ **AV1 codec** (if available)

## Why Authentication is Required

According to [Twitch's documentation](https://help.twitch.tv/s/article/2k-streaming):

> **Why can't I see certain quality levels?**
> - **You are not logged in**: Higher resolution playback is currently limited to logged-in viewers. Logged-out viewers can still watch content in 1080p.
> - **Location restrictions**: Higher resolution playback is currently restricted in some regions.

Streamlink (the tool StreamVault uses) runs **unauthenticated by default**, so Twitch treats it like a logged-out viewer → **1080p max**.

## How to Get Your OAuth Token

### Step 1: Login to Twitch

Open [twitch.tv](https://twitch.tv) in your browser and login with your account.

### Step 2: Open Developer Console

Press **F12** (or **Ctrl+Shift+I** on Windows/Linux, **Cmd+Option+I** on Mac) to open Developer Tools.

### Step 3: Navigate to Console Tab

Click on the **Console** tab in the Developer Tools.

### Step 4: Extract OAuth Token

Copy and paste this JavaScript command into the console:

```javascript
document.cookie.split("; ").find(item=>item.startsWith("auth-token="))?.split("=")[1]
```

Press **Enter**. You should see a string of ~30 alphanumeric characters:

```
"abcdefghijklmnopqrstuvwxyz0123"
```

**Copy this token** (without the quotes).

### Step 5: Add to Environment Variables

#### Docker Compose (.env file)

Add to your `.env` file:

```env
TWITCH_OAUTH_TOKEN=abcdefghijklmnopqrstuvwxyz0123
```

Then restart the container:

```bash
docker compose -f docker/docker-compose.yml down
docker compose -f docker/docker-compose.yml up -d
```

**StreamVault will automatically**:
1. ✅ Generate `/app/config/streamlink/config.twitch` with your token
2. ✅ Enable H.265/1440p quality options in the UI
3. ✅ Log OAuth status at startup

**You do NOT need to manually edit any config files!**

#### Docker Run

Add the environment variable:

```bash
docker run -d \
  -e TWITCH_OAUTH_TOKEN=abcdefghijklmnopqrstuvwxyz0123 \
  # ... other environment variables
  frequency2098/streamvault
```

## Verify H.265/1440p is Working

### Check Frontend Quality Dropdown

After configuring OAuth token and restarting:

1. **Open StreamVault Web UI**
2. **Go to Settings → Streamers**
3. **Click on a streamer → Recording Settings**
4. **Quality dropdown should show**:
   - ✅ "1440p 60fps (H.265)" - **ENABLED** (if OAuth configured)
   - ✅ "1080p 60fps" - ENABLED
   - ✅ "720p 60fps" - ENABLED
   - etc.

**Without OAuth**:
- ❌ "1440p 60fps (H.265)" - **DISABLED** (grayed out)
- 💡 Tooltip: "Requires TWITCH_OAUTH_TOKEN to be configured"

### Check Streamlink Config File

```bash
# Inside Docker container
docker exec streamvault cat /app/config/streamlink/config.twitch
```

**With OAuth configured**:
```
twitch-api-header=Authorization=OAuth abcdefghij...
```

**Without OAuth**:
```
# twitch-api-header=Authorization=OAuth YOUR_TOKEN_HERE
```

### Check Streamlink Logs

After starting a recording, check the streamlink logs:

```bash
# Inside Docker container
tail -f /app/logs/streamlink/*.log

# Or download from host
docker exec streamvault cat /app/logs/streamlink/streamlink_*.log
```

Look for these lines:

```
[cli][info] Available streams: audio_only, 360p30 (worst), 480p30, 720p60, 1080p60, 1440p60 (best)
[plugins.twitch][debug] Using codecs: h265, h264
```

**With OAuth**:
- ✅ `1440p60` appears in available streams
- ✅ `Using codecs: h265, h264` (or `av1, h265, h264`)

**Without OAuth** (or invalid token):
- ❌ Only `1080p60 (best)` - no 1440p
- ❌ Only `h264` codec available

### Check Recording Properties

After a recording finishes, check the video file properties:

```bash
ffprobe /recordings/streamer_name/video_file.mp4
```

Look for:

```
Stream #0:0: Video: hevc (Main) [hev1], yuv420p, 2560x1440, ...
```

- **Codec**: `hevc` = H.265/HEVC ✅
- **Resolution**: `2560x1440` = 1440p ✅

Compare with unauthenticated recording:

```
Stream #0:0: Video: h264 (High) [avc1], yuv420p, 1920x1080, ...
```

- **Codec**: `h264` = H.264/AVC
- **Resolution**: `1920x1080` = 1080p

## Token Expiration & Renewal

Twitch OAuth tokens from cookies **expire after ~60 days**. If recordings suddenly drop back to 1080p:

1. **Re-extract the token** using the steps above
2. **Update `.env`** with the new token
3. **Restart the container**

### Automation (Advanced)

For automatic token renewal, you could:
- Use Twitch's official OAuth flow (requires web server callback)
- Store refresh token in database (complex)
- Use browser automation (e.g., Playwright/Puppeteer)

**Not implemented yet** - manual renewal required for now.

## Troubleshooting

### ❌ Still Getting 1080p Only

**Check 1**: Verify token is set correctly

```bash
docker exec streamvault env | grep TWITCH_OAUTH_TOKEN
```

Should show:
```
TWITCH_OAUTH_TOKEN=abcdefghijklmnopqrstuvwxyz0123
```

**Check 2**: Check streamlink logs for authentication

```bash
docker exec streamvault cat /app/logs/streamlink/*.log | grep -i "authorization\|oauth"
```

Should show:
```
[cli][debug] Using Twitch OAuth authentication for streamer_name (H.265/1440p enabled)
```

**Check 3**: Verify token is valid

The token might have expired. Re-extract from browser cookies.

### ❌ Token Extraction Returns `undefined`

**Cause**: You're not logged into Twitch, or the cookie name changed.

**Fix**: 
1. Ensure you're logged into Twitch
2. Try this alternative command:

```javascript
document.cookie.split("; ").map(c => c.split("=")).find(([k]) => k === "auth-token")?.[1]
```

### ❌ StreamVault Logs Show "Proxy connection failed"

OAuth token works independently of proxy settings. If you see proxy errors:

1. **Check proxy configuration** in Settings → Proxy
2. **Disable proxy** temporarily to test OAuth
3. OAuth + Proxy should work together if both configured correctly

## Security Considerations

### Token Storage

- ✅ Token stored in **environment variables** (not in code)
- ✅ Token **NOT logged** to files (except at startup: "OAuth configured")
- ✅ **Auto-generated** config file at `/app/config/streamlink/config.twitch`
- ✅ Config regenerated on every startup (always up-to-date)

### Token Exposure

**Risk**: OAuth token grants access to your Twitch account.

**Mitigation**:
- Use a **dedicated Twitch account** for StreamVault (not your main account)
- Token only allows **reading streams** (no write permissions)
- Regularly rotate tokens (every 30-60 days)
- Config file not committed to git (in `.gitignore`)

### Multi-User Deployments

If StreamVault is used by multiple people:
- Token grants access based on the **token owner's location/region**
- All recordings use the **same token** (global setting)
- Consider using a **shared/bot account** token

## Implementation Details

### Automatic Config Generation

StreamVault **automatically** generates `/app/config/streamlink/config.twitch` at startup:

```python
# app/services/system/streamlink_config_service.py
def update_config_from_settings():
    """Generate Streamlink config from environment variables and settings"""
    - Read TWITCH_OAUTH_TOKEN from settings
    - Read HTTP_PROXY, HTTPS_PROXY from settings
    - Generate config.twitch with all static options
    - Write to /app/config/streamlink/config.twitch
```

**Config includes:**
- ✅ OAuth authentication header (if token set)
- ✅ Codec preferences (av1, h265, h264)
- ✅ Proxy settings (if configured)
- ✅ Static streamlink options (timeouts, retries, etc.)

**Config does NOT include** (set per-recording):
- ❌ Quality (changes per streamer)
- ❌ Output path (changes per recording)
- ❌ Log file path (changes per streamer)

### Streamlink Command

StreamVault passes minimal arguments to Streamlink:

```bash
streamlink \
  twitch.tv/streamer_name \
  best \
  -o /recordings/output.ts \
  --logfile /app/logs/streamlink/streamer.log
```

**Everything else** comes from `/app/config/streamlink/config.twitch`!

### Code Locations

| File | Purpose |
|------|---------|
| `app/config/settings.py` | `TWITCH_OAUTH_TOKEN` environment variable |
| `app/services/system/streamlink_config_service.py` | Auto-generate config.twitch |
| `app/main.py` | Call `update_config_from_settings()` at startup |
| `app/utils/streamlink_utils.py` | `get_streamlink_command()` (minimal args) |
| `app/routes/settings.py` | `/api/settings/quality-options` endpoint |
| `config/streamlink/config.twitch` | Auto-generated (DO NOT EDIT!) |

### Environment Variable Flow

```
1. Docker .env file
   ↓
2. docker-compose.yml (environment section)
   ↓
3. Container environment variables
   ↓
4. app/config/settings.py (Pydantic Settings)
   ↓
5. process_manager.py (reads settings.TWITCH_OAUTH_TOKEN)
   ↓
6. streamlink_utils.py (adds --twitch-api-header)
   ↓
7. Streamlink subprocess (authenticated request to Twitch API)
```

## References

- [Twitch 2K Streaming Guide](https://help.twitch.tv/s/article/2k-streaming)
- [Streamlink Twitch Plugin Docs](https://streamlink.github.io/plugins/twitch.html#authentication)
- [Streamlink GitHub Issue #5370](https://github.com/streamlink/streamlink/issues/5370) (Client-Integrity Tokens)

## FAQ

### Q: Do I need a Twitch API app for this?

**A:** No. The `TWITCH_APP_ID` and `TWITCH_APP_SECRET` are for EventSub webhooks (stream notifications). The `TWITCH_OAUTH_TOKEN` is **separate** - it's your personal authentication cookie.

### Q: Will this work with multi-proxy setup?

**A:** Yes! OAuth authentication and proxy settings are independent:
- **OAuth**: Authenticates as logged-in user → enables H.265/1440p
- **Proxy**: Routes traffic through different IPs → avoids rate limiting

Both can be used together.

### Q: What if the streamer doesn't stream in 1440p?

**A:** If the broadcaster only streams 1080p, you'll still get H.265 codec (better quality than H.264 at same resolution). Check their stream quality on Twitch web player:
- Settings → Quality → Should show "1440p" if they stream it
- Check their codec: F12 → Console → Right-click video → "Stats for nerds" → Look for `hev1` (H.265)

### Q: Can I use a bot account token?

**A:** Yes! Create a separate Twitch account, login, extract the token. This is **recommended** for security (don't use your main account token).

---

**Last Updated**: November 16, 2024  
**StreamVault Version**: 2.0.0+

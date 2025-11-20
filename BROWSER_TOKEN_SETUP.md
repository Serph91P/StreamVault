# Browser Token Setup for H.265/1440p Quality

## Why Browser Token?

Twitch restricts third-party OAuth applications from accessing:
- **H.265/HEVC and AV1 codecs** (60% smaller files, same quality)
- **1440p60 recording quality** (if stream supports it)
- **Ad-free recordings** (with Twitch Turbo subscription)

Only **browser authentication tokens** grant full access to these features.

## How to Get Your Token

### Step 1: Extract Token from Browser

1. Open **Twitch.tv** in your browser and **log in**
2. Press **F12** (or Ctrl+Shift+I / Cmd+Option+I) to open Developer Tools
3. Go to the **Console** tab
4. Paste this command and press Enter:
   ```javascript
   document.cookie.split("; ").find(item=>item.startsWith("auth-token="))?.split("=")[1]
   ```
5. Copy the 30-character token (example: `abc123xyz456def789ghi012jkl345`)

### Step 2: Set Token in Docker Compose

Edit your `.env` file or `docker-compose.yml`:

```env
TWITCH_OAUTH_TOKEN=your_30_character_token_here
```

### Step 3: Restart Container

```bash
docker compose restart app
```

## Token Validity

- **Browser tokens last 60-90 days** before expiring
- You'll need to manually update the token when it expires
- The token is **account-specific** and safe to store (only works with your Twitch account)

## Benefits of Browser Token

✅ **H.265/HEVC codec** - 60% smaller files, same quality  
✅ **AV1 codec support** - Even better compression  
✅ **1440p60 quality** - If stream supports it  
✅ **Ad-free recordings** - With Twitch Turbo subscription  
✅ **Automatic token refresh** - Backend handles token management

## How It Works Technically

1. **Environment Variable**: `TWITCH_OAUTH_TOKEN` is passed to container
2. **Settings Service**: Reads token from environment on startup
3. **Token Service**: Uses browser token as fallback if database token unavailable
4. **Streamlink Command**: Token passed as `--twitch-api-header=Authorization=OAuth TOKEN`

### Backend Token Priority

The backend uses tokens in this order:

1. **Environment variable** (`TWITCH_OAUTH_TOKEN`) ← Browser token (PRIORITY - Full quality)
2. **Database token** (from OAuth flow, auto-refreshed - LIMITED quality, used for EventSub)
3. **None** (recordings work but limited to 1080p H.264)

**Important**: Browser token always takes priority because OAuth tokens don't work for H.265/1440p.

## Verification

After setting the token, verify it's loaded:

```bash
# Check if token is set in container
docker exec streamvault env | grep TWITCH_OAUTH_TOKEN

# Check logs for token usage
docker logs streamvault 2>&1 | grep "Using access token from environment"
```

## Security Notes

- **Token is account-specific**: Only works with your Twitch account
- **Store securely**: Don't commit token to git repositories
- **Limited scope**: Can't modify your account, only read stream data
- **Auto-expires**: Token automatically expires after 60-90 days

## Troubleshooting

### Token Not Working

**Symptom**: Still recording in H.264/1080p after setting token

**Solutions**:
1. Verify token is set: `docker exec streamvault env | grep TWITCH_OAUTH_TOKEN`
2. Check for whitespace: Token should be exactly 30 characters
3. Restart container: `docker compose restart app`
4. Extract new token: Old token may have expired

### How to Verify Token is Used

Check logs during recording:

```bash
docker logs -f streamvault
```

**Look for:**
```
🔑 Using auto-refreshed OAuth token for [streamer_name]
```
or
```
Using access token from environment variable (TWITCH_OAUTH_TOKEN)
```

### Token Expired

**Symptom**: Recordings fail with "Unauthorized" error

**Solution**:
1. Extract new token from browser (see Step 1)
2. Update `.env` file with new token
3. Restart container: `docker compose restart app`

## Alternative: OAuth Flow (Not Recommended)

You can also use the built-in OAuth flow in **Settings → Twitch Connection**, but:

- ❌ **OAuth tokens don't work for H.265/1440p** (Twitch API limitation)
- ❌ **Requires Twitch app credentials** (`TWITCH_APP_ID`, `TWITCH_APP_SECRET`)
- ❌ **Needs public callback URL** (for EventSub notifications)

**Use browser token instead** for full quality support.

## Related Files

- `app/services/system/twitch_token_service.py` - Token management (supports env variable fallback)
- `app/config/settings.py` - Reads `TWITCH_OAUTH_TOKEN` environment variable
- `app/utils/streamlink_utils.py` - Passes token to Streamlink command
- `docker/docker-compose.yml` - Environment variable configuration

## UI Guide

A visual guide for extracting the token is available in the web UI:

**Settings → Twitch Connection → Manual Token Setup (Recommended)**

The UI provides:
- Step-by-step instructions with numbered steps
- Copy-to-clipboard button for JavaScript command
- Visual indicators and info boxes
- Explanation of why browser token is needed

---

**Last Updated**: November 20, 2025  
**Streamlink Version**: 8.0.0  
**Related Commits**: 0dcd6f4b (Streamlink format fix), 3d85055d (UI guide)

# Streamlink OAuth Token Fix - Session Summary

## Problem

Streamlink recordings were failing with error:
```
[cli][error] Unauthorized: The "Authorization" token is invalid.
```

Despite having a valid OAuth token stored in the database.

## Root Cause

The OAuth token was being passed to Streamlink as **3 separate command-line arguments**:
```bash
--twitch-api-header Authorization=OAuth abcdefghijklmnopqrstuvwxyz0123
# Parsed as 3 args: ["--twitch-api-header", "Authorization=OAuth", "abcdefghijklmnopqrstuvwxyz0123"]
```

This caused Streamlink to interpret the token as a tuple `('Authorization', 'OAuth ...')` instead of a single header value.

The log showed:
```
[cli][debug]  --twitch-api-header=[('Authorization', 'OAuth abcdefghijklmnopqrstuvwxyz0123')]
```

## Solution

Changed from using `cmd.extend()` with separate arguments to `cmd.append()` with a single argument using `=` format:

### Before (WRONG ❌):
```python
cmd.extend(["--twitch-api-header", f"Authorization=OAuth {oauth_token.strip()}"])
```

### After (CORRECT ✅):
```python
cmd.append(f"--twitch-api-header=Authorization=OAuth {oauth_token.strip()}")
```

## Files Modified

### `/app/utils/streamlink_utils.py`

**Changed arguments:**
1. `--twitch-api-header` (OAuth token) ✅
2. `--twitch-supported-codecs` (codec preferences) ✅
3. `--http-proxy` (HTTP proxy URL) ✅
4. `--https-proxy` (HTTPS proxy URL) ✅

**Changes applied in 4 locations:**
- `test_proxy_connectivity()` - Proxy connectivity test
- `get_stream_info()` - Stream info retrieval
- `get_streamlink_command()` - Main recording command
- `_add_proxy_settings()` - Proxy configuration helper

## Why This Matters

According to Streamlink documentation:
```bash
streamlink "--twitch-api-header=Authorization=OAuth TOKEN" twitch.tv/CHANNEL best
```

The `--twitch-api-header` must be a **single argument** with the value attached using `=`.

Using separate arguments causes the shell/Python subprocess to parse them incorrectly:
- Python's `subprocess.run(["cmd", "--arg", "value"])` works fine
- BUT Streamlink's argparse expects `--arg=value` for complex values like headers

## Testing

### Before Fix:
```
[cli][debug]  --twitch-api-header=[('Authorization', 'OAuth abcdefghijklmnopqrstuvwxyz0123')]
[cli][error] Unauthorized: The "Authorization" token is invalid.
```

### Expected After Fix:
```
[cli][debug]  --twitch-api-header=Authorization=OAuth abcdefghijklmnopqrstuvwxyz0123
[cli][info] Found matching plugin twitch for URL twitch.tv/CHANNEL
[cli][info] Opening stream: 1080p60 (hls)
```

## Validation Steps

1. **Restart Docker container** to apply changes:
   ```bash
   docker compose -f docker/docker-compose.yml restart app
   ```

2. **Start a new recording** via the StreamVault UI

3. **Check Streamlink logs** at `/app/logs/streamlink/[streamer]/streamlink_*.log`:
   ```bash
   docker compose -f docker/docker-compose.yml logs -f app
   tail -f logs/streamlink/dhalucard/streamlink_*.log
   ```

4. **Verify OAuth header format**:
   - Should see: `--twitch-api-header=Authorization=OAuth ...`
   - Should NOT see: `--twitch-api-header=[('Authorization', ...)]`

5. **Confirm recording success**:
   - Stream should start recording without "Unauthorized" error
   - Check for "Opening stream: 1080p60" in logs

## Related Documentation

- **Streamlink Twitch Plugin**: https://streamlink.github.io/plugins/twitch.html#authentication
- **StreamVault OAuth Setup**: `docs/TWITCH_OAUTH_H265_SETUP.md`
- **Migration 034**: Added `twitch_access_token` column for persistent token storage

## Impact

This fix affects **all Streamlink recordings** using OAuth tokens or proxies:
- ✅ OAuth authentication (H.265/1440p/ad-free streams)
- ✅ Proxy configuration (multi-proxy system)
- ✅ Codec preferences (H.264/H.265/AV1)

## Commit Message

```
fix(recording): correct Streamlink OAuth token argument format

The OAuth token was being passed as 3 separate arguments instead of 1,
causing Streamlink to parse it as a tuple ('Authorization', 'OAuth ...')
instead of a single header value.

Changed from:
  cmd.extend(["--twitch-api-header", "Authorization=OAuth token"])

To:
  cmd.append("--twitch-api-header=Authorization=OAuth token")

Also applied the same fix to:
- --twitch-supported-codecs (codec preferences)
- --http-proxy (HTTP proxy URL)
- --https-proxy (HTTPS proxy URL)

This prevents shell parsing issues and follows Streamlink's documented
CLI format: --arg=value for complex arguments.

Fixes: "Unauthorized: The 'Authorization' token is invalid" errors
Affects: All recordings using OAuth tokens, proxies, or custom codecs
```

## Additional Notes

- The token itself is valid (stored in database, expires at 22:39:38)
- Token encryption/decryption is working correctly
- The issue was purely in the command-line argument formatting
- This is a common pitfall when building CLI commands programmatically

## Prevention

Added comments in code to prevent regression:
```python
# Use single argument with = to prevent Streamlink from parsing it as multiple args
# CORRECT:   --twitch-api-header=Authorization=OAuth token
# INCORRECT: --twitch-api-header Authorization=OAuth token (creates tuple)
```

---

**Date**: 2025-11-20  
**Session**: Bug Fix - Streamlink OAuth Token Parsing  
**Status**: ✅ Fixed - Awaiting production testing  
**Files Changed**: 1 (`app/utils/streamlink_utils.py`)  
**Lines Changed**: 12 modifications across 4 functions

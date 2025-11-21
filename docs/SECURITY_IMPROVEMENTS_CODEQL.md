# Security Improvements for CodeQL Compliance

This document describes the security improvements made to address CodeQL warnings.

## Overview

Two main security vulnerabilities were addressed:
1. **CWE-532**: Clear-text logging of sensitive information
2. **CWE-601**: URL redirection from remote source (Open Redirect)

## 1. Clear-text Logging of Sensitive Information (CWE-532)

### Problem
Streamlink and FFmpeg commands containing OAuth tokens and proxy credentials were being logged to files without sanitization, exposing sensitive data in plain text.

### Solution
Implemented `sanitize_command_for_logging()` function in `app/utils/security.py` that automatically redacts:
- OAuth tokens: `--twitch-api-header=Authorization=OAuth [REDACTED]`
- Proxy URLs with credentials: `--http-proxy=[REDACTED]`
- Generic sensitive flags: `--password=`, `--token=`, `--api-key=`, `--secret=`

### Changes Made

#### Modified: `app/services/system/logging_service.py`

**Function: `log_streamlink_start()`**
- Added import: `from app.utils.security import sanitize_command_for_logging`
- Sanitize command before logging: `safe_cmd = sanitize_command_for_logging(cmd)`
- Use `safe_cmd` in both file writes and logger calls

**Function: `log_ffmpeg_start()`**
- Added import: `from app.utils.security import sanitize_command_for_logging`
- Sanitize command before logging: `safe_cmd = sanitize_command_for_logging(cmd)`
- Use `safe_cmd` in both file writes and logger calls

### Example

**Before:**
```
Command: streamlink --twitch-api-header=Authorization=OAuth abc123xyz456 twitch.tv/streamer best
```

**After:**
```
Command: streamlink --twitch-api-header=[REDACTED] twitch.tv/streamer best
```

## 2. URL Redirection from Remote Source (CWE-601)

### Problem
User-provided redirect URLs could potentially be exploited for open redirect attacks, allowing attackers to redirect users to malicious external sites.

### Solution
Implemented `validate_redirect_url()` function in `app/utils/security.py` with:
- Whitelist-based validation (only allows specific paths)
- Blocks absolute URLs (`http://`, `https://`, `//`)
- Blocks malicious schemes (`javascript:`, `data:`)
- Returns safe default if validation fails

### Usage

**Location: `app/routes/twitch_auth.py`**

```python
# Line 55: Error redirect validation
safe_error_url = validate_redirect_url(state if state else "/add-streamer", "/add-streamer")
return RedirectResponse(url=f"{safe_error_url}?error=auth_failed")

# Line 86: Success redirect validation
safe_state = validate_redirect_url(state if state else "/settings", "/settings")
return RedirectResponse(url=f"{safe_state}?token={access_token}&auth_success=true")
```

### Allowed Redirect Paths (Whitelist)

```python
ALLOWED_REDIRECT_PATHS = {
    "/settings",
    "/add-streamer",
    "/streamers",
    "/",
    "/home"
}
```

### Example

**Attack Attempt:**
```
state=https://evil.com
```

**Result:**
```
Blocked and returns default: /settings
```

## Security Testing

Both security functions have comprehensive test coverage in `tests/test_security.py`:

### Test Coverage

#### `sanitize_command_for_logging()`
- ✅ OAuth token redaction in Twitch API headers
- ✅ Proxy URL redaction (with credentials)
- ✅ Generic password/token/API key redaction
- ✅ Edge cases (empty list, None, non-list types)

#### `validate_redirect_url()`
- ✅ Valid relative paths allowed
- ✅ Absolute URLs blocked (`http://`, `https://`)
- ✅ Protocol-relative URLs blocked (`//evil.com`)
- ✅ Malicious schemes blocked (`javascript:`, `data:`)
- ✅ Non-whitelisted paths blocked
- ✅ Empty/invalid input handling

## Running Tests

```bash
# Run security tests
python -m pytest tests/test_security.py -v

# Run specific test classes
python -m pytest tests/test_security.py::TestCommandSanitization -v
python -m pytest tests/test_security.py::TestURLRedirectValidation -v
```

## Impact

### Before Fixes
- OAuth tokens logged in clear text in log files
- Proxy credentials exposed in log files
- Potential for open redirect attacks via OAuth state parameter

### After Fixes
- All sensitive data redacted in logs: `[REDACTED]`
- Only whitelisted redirect paths allowed
- Security events logged for monitoring and alerting
- CodeQL warnings resolved

## Future Considerations

1. **Log Rotation**: Ensure old logs with sensitive data are rotated and purged
2. **Access Control**: Restrict access to log files (already in place via file permissions)
3. **Monitoring**: Set up alerts for `OPEN_REDIRECT_BLOCKED` events
4. **Audit**: Periodically review whitelist paths and add new ones as needed

## References

- CWE-532: Information Exposure Through Log Files
  - https://cwe.mitre.org/data/definitions/532.html
- CWE-601: URL Redirection to Untrusted Site ('Open Redirect')
  - https://cwe.mitre.org/data/definitions/601.html
- OWASP Cheat Sheet: Logging
  - https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

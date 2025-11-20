# Streamlink Command-Line Argument Best Practices

## ⚠️ Critical Rule: Complex Arguments Must Use `=` Format

When building Streamlink commands programmatically in Python, **always use the `--arg=value` format for complex arguments** (headers, URLs, tokens, etc.).

### ❌ WRONG - Separate Arguments (causes parsing errors)
```python
cmd.extend(["--twitch-api-header", "Authorization=OAuth token"])
# Result: 2 args → ["--twitch-api-header", "Authorization=OAuth token"]
# Streamlink interprets as: header name + value separately
# Creates tuple: ('Authorization', 'OAuth token')
```

### ✅ CORRECT - Single Argument with `=`
```python
cmd.append("--twitch-api-header=Authorization=OAuth token")
# Result: 1 arg → ["--twitch-api-header=Authorization=OAuth token"]
# Streamlink interprets as: single header with full value
# Correct format: "Authorization=OAuth token"
```

## Arguments That MUST Use `=` Format

| Argument | Reason | Example |
|----------|--------|---------|
| `--twitch-api-header` | Contains spaces and special chars | `--twitch-api-header=Authorization=OAuth abc123` |
| `--http-proxy` | URLs may contain special chars | `--http-proxy=http://user:pass@host:8080` |
| `--https-proxy` | URLs may contain special chars | `--https-proxy=https://user:pass@host:8443` |
| `--twitch-supported-codecs` | Comma-separated list | `--twitch-supported-codecs=h264,h265,av1` |

## Arguments Safe with Separate Format

These are safe to use with `cmd.extend(["--arg", "value"])` because they never contain spaces:

- `-o` / `--output` (file paths without spaces)
- `--loglevel` (single word: debug, info, etc.)
- `--retry-streams` (single number)
- `--stream-timeout` (single number)

## Code Pattern

```python
# For complex/sensitive arguments → Use append with =
cmd.append(f"--twitch-api-header=Authorization=OAuth {token}")
cmd.append(f"--http-proxy={proxy_url}")

# For simple arguments → Either works
cmd.extend(["-o", output_path])  # OK
cmd.extend(["--loglevel", "debug"])  # OK
```

## Why This Matters

Python's `subprocess.run()` passes arguments correctly to the shell, but **Streamlink's internal argument parser** (argparse) has specific expectations:

1. **With separate args**: `["--twitch-api-header", "Authorization=OAuth token"]`
   - Argparse sees 2 tokens
   - First token: `--twitch-api-header`
   - Second token: `Authorization=OAuth token`
   - Tries to parse as key-value pair → Creates tuple

2. **With single arg**: `["--twitch-api-header=Authorization=OAuth token"]`
   - Argparse sees 1 token
   - Splits on first `=`
   - Key: `--twitch-api-header`
   - Value: `Authorization=OAuth token`
   - Correctly interprets as HTTP header

## Streamlink Documentation Reference

From https://streamlink.github.io/plugins/twitch.html#authentication:

```bash
streamlink "--twitch-api-header=Authorization=OAuth TOKEN" twitch.tv/CHANNEL best
```

Notice the **quotes around the entire argument** and the **`=` between flag and value**.

## Testing Argument Format

To verify correct format, check Streamlink debug logs:

### ✅ Correct Format
```
[cli][debug]  --twitch-api-header=Authorization=OAuth abc123
```

### ❌ Incorrect Format (tuple)
```
[cli][debug]  --twitch-api-header=[('Authorization', 'OAuth abc123')]
```

## Historical Context

This issue was discovered in StreamVault on 2025-11-20:
- **Symptom**: "Unauthorized: The 'Authorization' token is invalid"
- **Cause**: Token passed as 3 separate args instead of 1
- **Fix**: Changed from `cmd.extend()` to `cmd.append()` with `=` format
- **Files**: `app/utils/streamlink_utils.py` (4 functions)

See: `docs/BUGFIX_STREAMLINK_OAUTH_FORMAT.md`

## Quick Checklist

When adding new Streamlink arguments:

- [ ] Does the value contain spaces? → Use `=` format
- [ ] Does the value contain special characters? → Use `=` format  
- [ ] Is it a URL or token? → Use `=` format
- [ ] Is it a comma-separated list? → Use `=` format
- [ ] Does Streamlink docs show quotes? → Use `=` format
- [ ] When in doubt → Use `=` format (always safe!)

---

**Remember**: `cmd.append(f"--arg={value}")` is **always safe** and prevents parsing issues. Only use `cmd.extend(["--arg", value])` for simple single-word values.

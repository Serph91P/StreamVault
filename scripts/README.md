# StreamVault - Safe Update Scripts

Scripts for safely updating StreamVault without interrupting active recordings.

## 📋 Scripts Overview

### 1. `check_safe_to_update.sh`
Checks if any recordings are currently active.

**Usage:**
```bash
# Simple check (exit 0 if safe, 1 if not)
./scripts/check_safe_to_update.sh

# Wait for recordings to finish (up to 60 minutes)
./scripts/check_safe_to_update.sh --wait --max-wait-minutes 60
```

**Exit Codes:**
- `0` - Safe to update (no active recordings)
- `1` - Not safe (recordings in progress)
- `2` - Error checking status

**Examples:**
```bash
# Use in CI/CD pipelines
./scripts/check_safe_to_update.sh && docker-compose restart

# Wait for recordings to finish before updating
./scripts/check_safe_to_update.sh --wait --max-wait-minutes 30 && ./deploy.sh
```

---

### 2. `safe_docker_update.sh`
Fully automated Docker update with recording protection.

**Usage:**
```bash
# Safe update (waits for recordings to finish)
./scripts/safe_docker_update.sh

# Force update (skip recording check - DANGEROUS)
./scripts/safe_docker_update.sh --force

# Custom wait time
./scripts/safe_docker_update.sh --max-wait-minutes 120
```

**What it does:**
1. ✅ Checks for active recordings
2. ✅ Waits for them to finish (optional timeout)
3. ✅ Pulls latest Docker images
4. ✅ Stops containers
5. ✅ Starts updated containers
6. ✅ Verifies services are running

**Examples:**
```bash
# Safe update with 30-minute timeout
./scripts/safe_docker_update.sh --max-wait-minutes 30

# Emergency update (interrupts recordings)
./scripts/safe_docker_update.sh --force
```

---

## 🔌 API Endpoint

### `GET /api/status/recordings-active`

Check recording status programmatically.

**Response:**
```json
{
  "has_active_recordings": false,
  "active_count": 0,
  "safe_to_update": true,
  "active_streamers": [],
  "timestamp": "2025-11-09T10:30:00Z",
  "message": "No active recordings - safe to update"
}
```

**Example with active recordings:**
```json
{
  "has_active_recordings": true,
  "active_count": 2,
  "safe_to_update": false,
  "active_streamers": ["CohhCarnage", "Bonjwa"],
  "timestamp": "2025-11-09T10:30:00Z",
  "message": "2 recording(s) in progress - wait before updating"
}
```

**cURL Example:**
```bash
curl http://localhost:8000/api/status/recordings-active
```

---

## 🚀 CI/CD Integration Examples

### GitHub Actions
```yaml
name: Deploy StreamVault

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Check if safe to update
        run: |
          ssh user@server './streamvault/scripts/check_safe_to_update.sh --wait --max-wait-minutes 60'
      
      - name: Deploy
        run: |
          ssh user@server './streamvault/scripts/safe_docker_update.sh'
```

### GitLab CI
```yaml
deploy:
  stage: deploy
  script:
    - ssh user@server './streamvault/scripts/safe_docker_update.sh --max-wait-minutes 30'
  only:
    - main
```

### Jenkins
```groovy
stage('Deploy') {
  steps {
    sh '''
      ssh user@server './streamvault/scripts/check_safe_to_update.sh --wait'
      ssh user@server 'cd streamvault && docker-compose pull && docker-compose up -d'
    '''
  }
}
```

### Cron Job (Automatic Updates)
```bash
# /etc/cron.d/streamvault-update
# Update every Sunday at 3 AM if no recordings are active
0 3 * * 0 user /path/to/streamvault/scripts/safe_docker_update.sh --max-wait-minutes 120
```

---

## ⚙️ Configuration

### Environment Variables

**`STREAMVAULT_API_URL`**  
API endpoint for status checks (default: `http://localhost:8000`)

```bash
export STREAMVAULT_API_URL="http://streamvault.local:8000"
./scripts/check_safe_to_update.sh
```

---

## 🛡️ Safety Features

- ✅ **Zero-Downtime Updates** - Waits for recordings to finish
- ✅ **Automatic Retry** - Checks status periodically
- ✅ **Timeout Protection** - Prevents infinite waiting
- ✅ **Detailed Logging** - Shows which streamers are recording
- ✅ **Exit Codes** - Scriptable for automation
- ✅ **Force Mode** - Emergency updates when needed

---

## 📝 Requirements

- **jq** or **python3** (for JSON parsing)
- **curl** (for API calls)
- **docker-compose** or **docker compose** (for updates)

**Install dependencies (Ubuntu/Debian):**
```bash
sudo apt-get install jq curl
```

**Install dependencies (macOS):**
```bash
brew install jq curl
```

---

## 🐛 Troubleshooting

### "Failed to connect to StreamVault API"
**Solution:** Check if StreamVault is running:
```bash
docker-compose ps
curl http://localhost:8000/health
```

### "Neither jq nor python3 found"
**Solution:** Install jq:
```bash
sudo apt-get install jq  # Ubuntu/Debian
brew install jq          # macOS
```

### Scripts not executable
**Solution:** Make them executable:
```bash
chmod +x scripts/*.sh
```

---

## 📚 More Information

- **API Documentation**: `/docs` endpoint (Swagger UI)
- **Recording Status**: `/api/status/active-recordings`
- **System Status**: `/api/status/system`

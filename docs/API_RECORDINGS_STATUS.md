# API Endpunkt: Recordings Active Status

## Überblick

Der `/api/status/recordings-active` Endpunkt prüft, ob aktuell Aufnahmen laufen und gibt detaillierte Informationen zurück. Dieser Endpunkt wurde speziell für CI/CD-Pipelines und Update-Systeme entwickelt, um zu bestimmen, ob es sicher ist, Wartungsarbeiten oder Updates durchzuführen.

## Endpunkt Details

- **URL**: `/api/status/recordings-active`
- **Methode**: `GET`
- **Authentifizierung**: Keine (Status-Endpunkt)
- **Content-Type**: `application/json`

## Request

Keine Parameter erforderlich - einfacher GET-Request.

### Beispiel cURL

```bash
curl http://localhost:8000/api/status/recordings-active
```

### Beispiel mit fetch (JavaScript)

```javascript
const response = await fetch('http://localhost:8000/api/status/recordings-active');
const status = await response.json();
console.log(status.safe_to_update);
```

## Response

### Response Struktur

```json
{
  "has_active_recordings": boolean,
  "active_count": number,
  "safe_to_update": boolean,
  "active_streamers": string[],
  "timestamp": string,
  "message": string
}
```

### Response Felder

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `has_active_recordings` | `boolean` | `true` wenn mindestens eine Aufnahme läuft, `false` wenn keine Aufnahmen aktiv |
| `active_count` | `number` | Anzahl der aktuell laufenden Aufnahmen (0, 1, 2, ...) |
| `safe_to_update` | `boolean` | `true` wenn keine Aufnahmen laufen (sicher für Updates), `false` wenn Aufnahmen aktiv sind |
| `active_streamers` | `string[]` | Liste der Streamer-Namen, die aktuell aufgenommen werden (z.B. `["CohhCarnage", "Bonjwa"]`) |
| `timestamp` | `string` | ISO 8601 Zeitstempel der Abfrage (UTC) |
| `message` | `string` | Menschenlesbare Statusmeldung |

### Beispiel-Responses

#### Keine aktiven Aufnahmen (Safe to Update)

```json
{
  "has_active_recordings": false,
  "active_count": 0,
  "safe_to_update": true,
  "active_streamers": [],
  "timestamp": "2025-11-09T14:30:00.123456Z",
  "message": "No active recordings - safe to update"
}
```

#### Eine aktive Aufnahme

```json
{
  "has_active_recordings": true,
  "active_count": 1,
  "safe_to_update": false,
  "active_streamers": ["CohhCarnage"],
  "timestamp": "2025-11-09T14:30:00.123456Z",
  "message": "1 recording(s) in progress - wait before updating"
}
```

#### Mehrere aktive Aufnahmen

```json
{
  "has_active_recordings": true,
  "active_count": 3,
  "safe_to_update": false,
  "active_streamers": ["CohhCarnage", "Bonjwa", "PietSmiet"],
  "timestamp": "2025-11-09T14:30:00.123456Z",
  "message": "3 recording(s) in progress - wait before updating"
}
```

## Funktionsweise (Technisch)

### Was der Endpunkt macht

1. **Datenbankabfrage**: 
   - Sucht alle Recordings mit `status = "recording"`
   - Joined mit `Stream` und `Streamer` Tabellen für vollständige Informationen
   - Nutzt `joinedload()` für optimierte Queries (kein N+1 Problem)

2. **Datenverarbeitung**:
   - Zählt aktive Aufnahmen
   - Extrahiert Streamer-Namen aus den Recordings
   - Fehlertolerante Verarbeitung (einzelne fehlerhafte Recordings brechen nicht die ganze Abfrage ab)

3. **Response-Generierung**:
   - `safe_to_update = (active_count == 0)` - Nur sicher wenn KEINE Aufnahmen laufen
   - Timestamp in UTC (ISO 8601 Format)
   - Menschenlesbare Nachricht basierend auf Status

### SQL-Query (vereinfacht)

```sql
SELECT recordings.*, streams.*, streamers.*
FROM recordings
INNER JOIN streams ON recordings.stream_id = streams.id
INNER JOIN streamers ON streams.streamer_id = streamers.id
WHERE recordings.status = 'recording';
```

## Verwendungszwecke

### 1. CI/CD Pipeline Integration

**Zweck**: Verhindere Docker-Updates während laufender Aufnahmen

```bash
#!/bin/bash
# GitHub Actions / GitLab CI / Jenkins

response=$(curl -s http://streamvault:8000/api/status/recordings-active)
safe=$(echo "$response" | jq -r '.safe_to_update')

if [ "$safe" = "true" ]; then
  echo "✅ Safe to update - no recordings active"
  docker-compose pull
  docker-compose up -d
  exit 0
else
  echo "❌ Not safe - recordings in progress"
  echo "$response" | jq -r '.message'
  exit 1
fi
```

### 2. Automatische Updates mit Wartezeit

**Zweck**: Warte bis keine Aufnahmen mehr laufen

```bash
#!/bin/bash
MAX_WAIT=60  # 60 Minuten

for i in $(seq 1 $MAX_WAIT); do
  safe=$(curl -s http://localhost:8000/api/status/recordings-active | jq -r '.safe_to_update')
  
  if [ "$safe" = "true" ]; then
    echo "✅ Safe to update after ${i} minutes"
    ./update.sh
    exit 0
  fi
  
  echo "⏳ Waiting... (${i}/${MAX_WAIT})"
  sleep 60
done

echo "❌ Timeout - still recording after ${MAX_WAIT} minutes"
exit 1
```

### 3. Monitoring & Alerting

**Zweck**: Benachrichtige wenn Aufnahmen länger als erwartet laufen

```python
import requests
import time

def check_long_running_recordings():
    response = requests.get("http://localhost:8000/api/status/recordings-active")
    data = response.json()
    
    if data["active_count"] > 0:
        streamers = ", ".join(data["active_streamers"])
        print(f"⚠️  {data['active_count']} recordings active: {streamers}")
        
        # Alert wenn seit 6 Stunden nicht safe to update
        # ... deine Alert-Logik ...
```

### 4. Web-Dashboard

**Zweck**: Zeige Live-Status in Admin-Panel

```typescript
// Vue/React Component
const checkRecordingStatus = async () => {
  const response = await fetch('/api/status/recordings-active');
  const data = await response.json();
  
  if (data.safe_to_update) {
    showUpdateButton(); // Zeige "Update jetzt möglich" Button
  } else {
    showWaitingMessage(data.active_streamers); // Zeige "Warte auf: CohhCarnage, ..."
  }
};
```

## Error Handling

### HTTP Status Codes

| Code | Bedeutung | Beschreibung |
|------|-----------|--------------|
| `200` | OK | Erfolgreiche Abfrage, siehe Response-Body für Details |
| `500` | Internal Server Error | Datenbankfehler oder anderer Server-Fehler |

### Error Response

```json
{
  "detail": "Failed to check active recordings status"
}
```

### Retry-Strategie

Bei 500-Fehlern empfohlen:
- Exponential Backoff (1s, 2s, 4s, 8s)
- Max 3-5 Retries
- Fallback: Annahme "Not Safe" (konservative Strategie)

```bash
# Beispiel mit Retry
for i in {1..3}; do
  response=$(curl -s -w "\n%{http_code}" http://localhost:8000/api/status/recordings-active)
  http_code=$(echo "$response" | tail -n1)
  
  if [ "$http_code" = "200" ]; then
    # Success
    break
  fi
  
  echo "❌ HTTP $http_code - Retry $i/3"
  sleep $((2**i))  # 2, 4, 8 Sekunden
done
```

## Performance

- **Antwortzeit**: < 50ms (typisch)
- **Datenbank-Queries**: 1 Query (optimiert mit `joinedload()`)
- **Cache**: Nicht implementiert (Status muss live sein)
- **Rate Limiting**: Nicht implementiert (Status-Endpunkt)

## Sicherheit

- **Keine Authentifizierung erforderlich**: Status ist nicht sensibel
- **Nur Lesezugriff**: Ändert keine Daten
- **SQL-Injection sicher**: Verwendet SQLAlchemy ORM (keine direkten SQL-Strings)
- **Path Traversal**: Nicht relevant (keine Dateisystemoperationen)

## Integration mit externen Scripts

Die Scripts im `/scripts` Verzeichnis nutzen diesen Endpunkt:

### `check_safe_to_update.sh`
- Prüft Status einmalig oder mit `--wait` Modus
- Exit Code 0 = safe, 1 = nicht safe, 2 = Fehler
- Nutzt `jq` oder Python für JSON-Parsing

### `safe_docker_update.sh`
- Ruft `check_safe_to_update.sh` auf
- Wartet optional bis Status safe ist
- Führt dann `docker-compose pull && docker-compose up -d` aus

Siehe `scripts/README.md` für Details.

## Best Practices

### ✅ DO

- Prüfe `safe_to_update` boolean für Entscheidungen (nicht `active_count`)
- Nutze `timestamp` um veraltete Responses zu erkennen
- Implementiere Timeouts (max 60-120 Minuten Wartezeit)
- Logge `active_streamers` für Debugging
- Zeige `message` dem User (bereits formatiert)

### ❌ DON'T

- Nicht nur `has_active_recordings` prüfen (nutze `safe_to_update`)
- Nicht endlos warten ohne Timeout
- Nicht HTTP 500 als "safe" interpretieren (konservativ sein)
- Nicht während Aufnahmen updaten (Datenverlust!)

## Beispiel: Vollständiges Update-Script

```bash
#!/bin/bash
set -e

API_URL="${STREAMVAULT_API_URL:-http://localhost:8000}"
MAX_WAIT_MINUTES=60
CHECK_INTERVAL=60  # Sekunden

echo "🔍 Checking if safe to update StreamVault..."

# Funktion: Status prüfen
check_status() {
    curl -s "${API_URL}/api/status/recordings-active" | jq -r '.safe_to_update'
}

# Wait Loop
for i in $(seq 1 $MAX_WAIT_MINUTES); do
    safe=$(check_status)
    
    if [ "$safe" = "true" ]; then
        echo "✅ Safe to update - no recordings active"
        
        # Update durchführen
        echo "📥 Pulling latest images..."
        docker-compose pull
        
        echo "🔄 Restarting containers..."
        docker-compose down
        docker-compose up -d
        
        echo "✅ Update completed successfully"
        exit 0
    fi
    
    # Status-Info
    active_count=$(curl -s "${API_URL}/api/status/recordings-active" | jq -r '.active_count')
    streamers=$(curl -s "${API_URL}/api/status/recordings-active" | jq -r '.active_streamers | join(", ")')
    
    echo "⏳ Waiting... ${i}/${MAX_WAIT_MINUTES} min - ${active_count} recording(s): ${streamers}"
    sleep $CHECK_INTERVAL
done

echo "❌ Timeout after ${MAX_WAIT_MINUTES} minutes - recordings still active"
exit 1
```

## Changelog

| Version | Datum | Änderung |
|---------|-------|----------|
| 1.0.0 | 2025-11-09 | Initial Release - Basic recording status check |

## Support

Bei Problemen:
1. Prüfe Logs: `docker logs streamvault-backend`
2. Teste manuell: `curl http://localhost:8000/api/status/recordings-active`
3. Checke Datenbank: `psql -c "SELECT COUNT(*) FROM recordings WHERE status='recording'"`

---

**Tipp**: Kombiniere diesen Endpunkt mit `/api/status/system` für vollständige Systemprüfungen vor Updates.

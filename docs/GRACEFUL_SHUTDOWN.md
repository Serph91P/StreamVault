# Graceful Shutdown in Docker

## Warum Graceful Shutdown wichtig ist

StreamVault führt laufende Aufnahmen durch, die bei einem harten Container-Stop korrupt werden können. Graceful Shutdown stellt sicher, dass:

- **Laufende Aufnahmen** ordnungsgemäß beendet werden
- **Temporäre Dateien** aufgeräumt werden
- **Datenbank-Transaktionen** vollständig abgeschlossen werden
- **WebSocket-Verbindungen** sauber geschlossen werden

## Docker-Integration

### Container-Signale

```bash
# Sendet SIGTERM an den Container
docker stop streamvault

# Nach 10 Sekunden: SIGKILL (hart)
docker stop -t 30 streamvault  # 30 Sekunden Timeout
```

### Dockerfile Setup

```dockerfile
# Stelle sicher, dass Python-Signale korrekt verarbeitet werden
ENV PYTHONUNBUFFERED=1

# Verwende exec form für korrektes Signal-Handling
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

```yaml
services:
  streamvault:
    build: .
    # Verlängere Shutdown-Timeout für laufende Aufnahmen
    stop_grace_period: 60s
    
    # Gesundheitsprüfung
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## Graceful Shutdown Ablauf

### 1. Signal-Empfang (SIGTERM)
```
🛑 Starting application shutdown...
```

### 2. Aufnahmen beenden (30s Timeout)
```
🔄 Gracefully shutting down recording service...
📹 Stopping active recording for stream 123...
📁 Finalizing recording files...
✅ Recording service shutdown completed
```

### 3. Services beenden
```
🔄 Stopping active recordings broadcaster...
🔄 Cancelling cleanup task...
🔄 Stopping EventSub...
```

### 4. Datenbank schließen
```
🔄 Closing database connections...
✅ Database connections closed
```

### 5. Shutdown complete
```
🎯 Application shutdown complete
```

## Kubernetes/Docker Swarm

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: streamvault
spec:
  template:
    spec:
      containers:
      - name: streamvault
        image: streamvault:latest
        # Graceful shutdown Zeit
        terminationGracePeriodSeconds: 60
        
        # Gesundheitsprüfung
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
```

### Rolling Updates

```bash
# Kubernetes: Graduelle Updates ohne Unterbrechung
kubectl set image deployment/streamvault streamvault=streamvault:v2.0.0

# Docker Swarm: Zero-Downtime Updates
docker service update --image streamvault:v2.0.0 streamvault
```

## Monitoring

### Logs überwachen
```bash
# Container-Logs in Echtzeit
docker logs -f streamvault

# Nur Shutdown-Logs
docker logs streamvault 2>&1 | grep "🛑\|🔄\|✅\|❌"
```

### Aufnahme-Status
```bash
# Aktive Aufnahmen vor Shutdown prüfen
curl http://localhost:8000/api/recording/active

# Gesundheitsstatus
curl http://localhost:8000/health
```

## Debugging

### Häufige Probleme

1. **Aufnahmen werden abgebrochen**
   ```
   ❌ Error during recording service shutdown: timeout
   ```
   → Verlängere `stop_grace_period` in docker-compose.yml

2. **Dateien bleiben korrupt**
   ```
   📁 Finalizing recording files...
   ❌ Error finalizing recording: file locked
   ```
   → Prüfe Dateiberechtigungen und Volumes

3. **Datenbank-Verbindungen bleiben offen**
   ```
   ❌ Error disposing database engine: connection pool exhausted
   ```
   → Prüfe Datenbank-Verbindungspool-Einstellungen

### Signal-Testing

```bash
# Teste Graceful Shutdown lokal
docker exec streamvault kill -TERM 1

# Überwache Shutdown-Prozess
docker exec streamvault tail -f /app/logs/streamvault.log
```

## Best Practices

1. **Immer `stop_grace_period` setzen** (mind. 60s)
2. **Gesundheitsprüfungen** implementieren
3. **Aufnahme-Status** vor Updates prüfen
4. **Backup-Strategie** für unterbrochene Aufnahmen
5. **Monitoring** für Shutdown-Prozesse

## Fazit

Graceful Shutdown ist in Docker-Umgebungen **essentiell** für:
- ✅ Datenintegrität
- ✅ Keine korrupten Aufnahmen
- ✅ Saubere Container-Updates
- ✅ Produktionstauglichkeit

Die Implementierung in StreamVault ist bereits vorbereitet und Docker-optimiert.

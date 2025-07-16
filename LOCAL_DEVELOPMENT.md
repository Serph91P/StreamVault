# StreamVault Local Development Guide

Dieses Dokument erklärt, wie du StreamVault lokal für Entwicklung und Tests ausführen kannst, ohne den umständlichen Deployment-Prozess durchlaufen zu müssen.

## 🚀 Schnellstart (Python lokal)

### 1. Abhängigkeiten installieren
```bash
pip install -r requirements.txt
```

### 2. Lokalen Server starten
```bash
python run_local.py
```

Das war's! Der Server läuft auf `http://localhost:8000`

- **Frontend**: `http://localhost:8000`
- **API Docs**: `http://localhost:8000/docs`
- **Admin Interface**: `http://localhost:8000/admin` (falls verfügbar)

## 🐳 Docker Local Setup (mit PostgreSQL)

### 1. Environment-Datei erstellen
```bash
cp .env.local .env
# Bearbeite .env und setze deine Twitch-Credentials
```

### 2. Docker Container starten
```bash
docker-compose -f docker-compose.local.yml up --build
```

### 3. Server stoppen
```bash
docker-compose -f docker-compose.local.yml down
```

## 📁 Verzeichnisstruktur für lokale Entwicklung

```
StreamVault/
├── streamvault_local.db        # SQLite Datenbank (Python lokal)
├── recordings_local/           # Lokale Aufnahmen
├── data_local/                # Lokale App-Daten
├── logs_local/                # Lokale Logs
├── .env                       # Environment-Variablen
└── run_local.py              # Lokaler Development Server
```

## 🔧 Entwicklungsoptionen

### Option 1: Python Lokal (Empfohlen für schnelle Tests)
- ✅ Keine Docker-Abhängigkeiten
- ✅ Sehr schneller Start (< 10 Sekunden)
- ✅ Hot Reload für Code-Änderungen
- ✅ SQLite Datenbank (keine PostgreSQL nötig)
- ✅ Einfaches Debugging

**Verwendung:**
```bash
python run_local.py
```

### Option 2: Docker Lokal
- ✅ Identisch zur Produktionsumgebung
- ✅ PostgreSQL Datenbank
- ✅ Hot Reload durch Volume Mounts
- ❌ Langsamerer Start (~30-60 Sekunden)

**Verwendung:**
```bash
docker-compose -f docker-compose.local.yml up --build
```

### Option 3: Hybrid (Python + PostgreSQL Container)
```bash
# Nur PostgreSQL in Docker starten
docker run --name postgres_local -e POSTGRES_USER=streamvault -e POSTGRES_PASSWORD=streamvault123 -e POSTGRES_DB=streamvault -p 5432:5432 -d postgres:16-alpine

# Environment-Variable setzen
export DATABASE_URL="postgresql://streamvault:streamvault123@localhost:5432/streamvault"

# Python lokal starten
python run_local.py
```

## 🔧 Konfiguration

### Environment-Variablen (.env)
```env
# Minimum für lokale Entwicklung
TWITCH_APP_ID=your_app_id
TWITCH_APP_SECRET=your_app_secret
BASE_URL=http://localhost:8000
EVENTSUB_SECRET=any_secret_here

# Für PostgreSQL (optional)
DATABASE_URL=postgresql://streamvault:streamvault123@localhost:5432/streamvault

# Für SQLite (Standard bei run_local.py)
# DATABASE_URL=sqlite:///./streamvault_local.db
```

### Twitch Credentials
Du brauchst:
1. Eine Twitch-App bei https://dev.twitch.tv/console/apps
2. `TWITCH_APP_ID` und `TWITCH_APP_SECRET`
3. `EVENTSUB_SECRET` (beliebiger String)

## 🐛 Debugging

### Logs ansehen
```bash
# Python lokal: Logs werden direkt in der Konsole angezeigt

# Docker lokal:
docker-compose -f docker-compose.local.yml logs -f app

# Nur Fehler:
docker-compose -f docker-compose.local.yml logs -f app | grep ERROR
```

### Datenbank zurücksetzen
```bash
# SQLite (Python lokal)
rm streamvault_local.db

# PostgreSQL (Docker)
docker-compose -f docker-compose.local.yml down -v
docker-compose -f docker-compose.local.yml up --build
```

### Frontend entwickeln
```bash
cd app/frontend
npm install
npm run dev  # Startet Vite dev server auf Port 5173
```

## 🔄 Workflow für Tests

1. **Code ändern** in `app/`
2. **Lokal testen** mit `python run_local.py`
3. **Funktionen prüfen** auf `http://localhost:8000`
4. **Bei OK**: Code committen

**Kein Docker-Build oder Server-Deployment nötig für schnelle Tests!**

## 🆘 Troubleshooting

### "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

### "Port already in use"
```bash
# Anderen Port verwenden
python -m uvicorn app.main:app --port 8001

# Oder prozess killen
lsof -ti:8000 | xargs kill -9  # macOS/Linux
netstat -ano | findstr :8000   # Windows
```

### "Database connection error"
- SQLite: Stelle sicher, dass du Schreibrechte im Verzeichnis hast
- PostgreSQL: Prüfe ob Container läuft: `docker ps`

### "Missing Twitch credentials"
- App funktioniert auch ohne echte Twitch-Credentials
- Manche Features sind ohne API-Zugang eingeschränkt

## 📋 Nützliche Befehle

```bash
# Server starten (Python)
python run_local.py

# Server starten (Docker)
docker-compose -f docker-compose.local.yml up --build

# Logs live verfolgen
tail -f logs_local/streamvault.log

# Datenbank-Migrations ausführen
python -c "from app.migrations_init import init_database; init_database()"

# Tests ausführen
python -m pytest tests/ -v

# Code formatieren
python -m black app/
python -m isort app/ --check

# Type checking
python -m mypy app/
```

# 🎨 Frontend Quick Start - Mock Mode

## Sofort loslegen (OHNE Docker):

```bash
# 1. In den Frontend-Ordner wechseln
cd app/frontend

# 2. Dependencies installieren (nur beim ersten Mal)
npm install

# 3. Dev-Server starten
npm run dev
```

**Öffne im Browser:** http://localhost:5173

---

## ✨ Was du jetzt siehst:

- ✅ **Dashboard** mit 2 Live-Streamern
- ✅ **3 Videos** in der Übersicht
- ✅ **Alle Settings-Seiten** mit Beispieldaten
- ✅ **Background Jobs** mit aktiven Tasks
- ✅ **Light/Dark Mode** umschaltbar
- ✅ **Alle UI-Komponenten** sichtbar und testbar

---

## 🔥 Hot Reload

Änderungen sind **sofort** sichtbar:

1. Öffne eine `.vue` oder `.scss` Datei
2. Speichere (`Ctrl+S`)
3. Browser aktualisiert automatisch - **KEIN Docker-Build!**

---

## 🎭 Mock-Daten anpassen

**Datei:** `app/frontend/src/mocks/mockData.ts`

```typescript
// Beispiel: Mehr Live-Streamer hinzufügen
export const mockStreamers = [
  {
    id: 5,
    username: 'deinstreamer',
    is_live: true,
    title: 'Mein Test-Stream',
    category_name: 'Just Chatting',
    viewer_count: 9999,
    // ... weitere Felder
  }
]
```

Speichern → Browser aktualisiert automatisch!

---

## 🌐 Mit echtem Backend verbinden

```bash
# 1. Backend starten (in separatem Terminal)
cd /home/maxe/Dokumente/private_projects/StreamVault
docker compose -f docker/docker-compose.yml up -d

# 2. Mock-Modus ausschalten
# Bearbeite: app/frontend/.env.development
VITE_USE_MOCK_DATA=false

# 3. Frontend neu starten
npm run dev
```

---

## 🐛 Probleme?

**Browser zeigt nichts an:**
- Öffne DevTools (F12) → Console
- Schaue nach Fehlermeldungen
- Stelle sicher dass Port 5173 frei ist

**Änderungen werden nicht angezeigt:**
- Hard Refresh: `Ctrl+Shift+R`
- Dev-Server neu starten

**"Cannot find module" Fehler:**
```bash
rm -rf node_modules
npm install
```

---

## 📖 Mehr Infos:

Siehe `app/frontend/DEVELOPMENT.md` für Details!

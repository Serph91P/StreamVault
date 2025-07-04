# Category Image System

Das neue Category Image System lädt automatisch Twitch Category Box Art Bilder herunter und speichert sie lokal für bessere Performance und Offline-Verfügbarkeit.

## Funktionen

### 🎯 **Automatisches Herunterladen**
- Bilder werden automatisch von Twitch's CDN geladen wenn eine neue Kategorie erkannt wird
- Mehrere URL-Formate werden versucht um die beste Kompatibilität zu gewährleisten
- Fallback auf FontAwesome Icons wenn Download fehlschlägt

### 🚀 **Performance Optimierungen**
- Lokale Zwischenspeicherung verhindert wiederholte Downloads
- Async/Background Downloads blockieren nicht die UI
- Intelligente Fallbacks für sofortige Anzeige

### 💾 **Speicherung**
- Bilder werden in `app/frontend/public/images/categories/` gespeichert
- Dateinamen sind URL-sicher und enthalten Hashes für Eindeutigkeit
- Automatische Bereinigung alter, nicht verwendeter Bilder

## API Endpoints

### `GET /api/categories/image/{category_name}`
Gibt die URL für ein Kategorie-Bild zurück. Startet automatisch Download falls nicht gecacht.

```json
{
  "category_name": "League of Legends",
  "image_url": "/images/categories/league_of_legends_a1b2c3d4.jpg"
}
```

### `POST /api/categories/preload-images`
Lädt mehrere Kategorie-Bilder im Hintergrund herunter.

```json
{
  "message": "Started preloading 5 category images",
  "categories": ["League of Legends", "Valorant", "Minecraft"]
}
```

### `GET /api/categories/cache-status`
Gibt Informationen über den Cache-Status zurück.

```json
{
  "cached_categories": 15,
  "failed_downloads": 2,
  "cache_directory": "/app/frontend/public/images/categories",
  "cached_categories_list": ["League of Legends", "Valorant", ...]
}
```

### `POST /api/categories/cleanup-images`
Bereinigt alte, nicht verwendete Bilder.

```json
{
  "message": "Cleaned up category images older than 30 days"
}
```

## Frontend Integration

### Vue Composable: `useCategoryImages`

```vue
<script setup>
import { useCategoryImages } from '@/composables/useCategoryImages'

const { getCategoryImage, preloadCategoryImages } = useCategoryImages()

// Automatische Bildauflösung
const imageUrl = getCategoryImage('League of Legends')
// Gibt zurück: "/images/categories/league_of_legends_a1b2c3d4.jpg" oder "icon:fa-gamepad"

// Preload für bessere UX
await preloadCategoryImages(['Valorant', 'Minecraft', 'Fortnite'])
</script>
```

### Template Integration

```vue
<template>
  <div class="category-image">
    <!-- Zeigt Bild wenn verfügbar, sonst Icon -->
    <img 
      v-if="!getCategoryImage(category).startsWith('icon:')"
      :src="getCategoryImage(category)"
      :alt="category"
    />
    <i 
      v-else
      :class="getCategoryImage(category).replace('icon:', '')"
    ></i>
  </div>
</template>
```

## Migration für bestehende Daten

Für bestehende StreamVault Installationen mit bereits vorhandenen Kategorien:

```bash
# Lädt alle Bilder für bereits existierende Kategorien herunter
python migrate_category_images.py
```

## Konfiguration

### Service-Konfiguration

```python
# In app/services/category_image_service.py
category_image_service = CategoryImageService(
    images_dir="app/frontend/public/images/categories"  # Anpassbar
)
```

### Twitch URL-Formate

Das System versucht mehrere URL-Formate:
1. `https://static-cdn.jtvnw.net/ttv-boxart/{category_name}-144x192.jpg`
2. `https://static-cdn.jtvnw.net/ttv-boxart/{url_encoded_name}-144x192.jpg`
3. `https://static-cdn.jtvnw.net/ttv-boxart/{space_to_percent20}-144x192.jpg`

### Icon Fallbacks

Für häufige Kategorien sind spezifische FontAwesome Icons definiert:

```javascript
const categoryIcons = {
  'Just Chatting': 'fa-comments',
  'League of Legends': 'fa-gamepad',
  'Valorant': 'fa-crosshairs',
  'Minecraft': 'fa-cube',
  'Grand Theft Auto V': 'fa-car',
  // ... weitere
}
```

## Wartung

### Automatische Bereinigung
```python
# Löscht Bilder die älter als 30 Tage sind
category_image_service.cleanup_old_images(days_old=30)
```

### Cache-Reset
```python
# Löscht alle gecachten Bilder
import shutil
shutil.rmtree("app/frontend/public/images/categories")
```

### Debugging
```python
# Cache-Status prüfen
status = await category_image_service.get_cache_status()
print(f"Cached: {status['cached_categories']}")
print(f"Failed: {status['failed_downloads']}")
```

## Vorteile

1. **🚀 Bessere Performance**: Lokale Bilder laden schneller
2. **🌐 Offline-Fähigkeit**: Funktioniert auch ohne Internetverbindung
3. **💿 Bandbreite sparen**: Keine wiederholten Downloads
4. **🎨 Anpassbarkeit**: Lokale Bilder können bearbeitet werden
5. **🛡️ Ausfallsicherheit**: Funktioniert auch wenn Twitch down ist
6. **🔄 Automatisch**: Keine manuelle Intervention erforderlich

Das System ist vollständig backward-kompatibel und erfordert keine Änderungen an bestehenden Komponenten!

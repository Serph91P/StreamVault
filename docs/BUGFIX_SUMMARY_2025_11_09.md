# Production Bug Fix Summary - Nov 9, 2025

## 🚨 Critical Bug: Segment Rotation ProcessLookupError

### Problem
**Alle Aufnahmen >24h sind seit dem 29. Oktober 2025 kaputt**

- **Symptom**: Streams laufen 4-15 Tage ohne Segment-Rotation → keine Post-Processing → leere Segment-Ordner
- **Betroffene Streams**: 
  - Bonjwa (Stream 348): 15 Tage kaputt
  - CohhCarnage (Stream 345): 15 Tage kaputt  
  - GiantWaffle (Stream 404): 5 Tage kaputt
  - Stream 413: 4 Tage kaputt

### Root Cause
**Streamlink-Prozesse sterben extern** (OOM Killer, Crash) während laufender Aufnahme:

1. Stream läuft >24h → `_should_rotate_segment()` = true
2. `_rotate_segment()` versucht alten Prozess zu stoppen
3. **Prozess ist bereits tot** (extern beendet) → `ProcessLookupError`
4. **Outer try-catch fängt Error** → Funktion endet
5. **Neues Segment wird NIE gestartet** → Stream stuck forever
6. **Post-Processing wird NIE getriggert** → leere Segment-Ordner
7. **Alle nachfolgenden Streams auch kaputt** → Recording-System blockiert

### Why Processes Die Externally
- **OOM Killer**: System RAM voll → Linux killt größten Prozess
- **Network Issues**: Proxy Timeout → Streamlink crash
- **Container Restart**: Docker/Kubernetes Maintenance
- **Streamlink Bugs**: Internal crashes bei sehr langen Streams (Tage/Wochen)

### Why uvloop is Special
StreamVault nutzt **uvloop** (high-performance event loop) statt standard asyncio:

```python
# Standard Python subprocess
process.poll()  # Returns None or returncode - NEVER throws

# uvloop (StreamVault)
process.poll()  # Can throw ProcessLookupError for zombie processes!
```

**Zombie Process** = Prozess terminiert aber noch nicht vom OS "aufgeräumt" (Status `Z` in Linux).

---

## ✅ Lösung

### Fix #1: Comprehensive Exception Handling
**Gesamte Process-Cleanup in try-catch mit finally-Block**:

```python
async def _rotate_segment(self, stream, segment_info, quality):
    try:
        process_id = f"stream_{stream.id}"
        
        if process_id in self.active_processes:
            current_process = self.active_processes[process_id]
            
            try:
                # Versuche Prozess zu stoppen (kann fehlschlagen)
                current_process.poll()
                if current_process.returncode is None:
                    current_process.terminate()
                    await asyncio.sleep(5)
                    current_process.poll()
                    if current_process.returncode is None:
                        current_process.kill()
                        
            except ProcessLookupError:
                # ✅ ERWARTET für extern beendete Prozesse
                logger.info("🔄 ROTATION: Process already terminated, continuing")
                
            except Exception as e:
                # ✅ Log aber NICHT stoppen
                logger.warning(f"🔄 ROTATION: Error: {e}, continuing anyway")
            
            finally:
                # ✅ KRITISCH: Immer aus Tracking entfernen
                self.active_processes.pop(process_id, None)
        
        # ✅ Dieser Code wird IMMER ausgeführt
        segment_info['segment_count'] += 1
        new_process = await self._start_segment(stream, next_path, quality)
        
        if new_process:
            logger.info(f"✅ Successfully rotated to segment {segment_info['segment_count']}")
            
    except Exception as e:
        logger.error(f"Critical rotation error: {e}", exc_info=True)
```

### Key Changes
1. **Graceful ProcessLookupError Handling** - INFO statt ERROR
2. **Finally Block for Cleanup** - IMMER Process aus `active_processes` entfernen
3. **Exception Isolation** - Cleanup-Errors stoppen Rotation nicht
4. **Better Logging** - Emoji-Prefixes für visuelle Log-Filterung

---

## 📊 Erwartetes Verhalten

### Vorher (KAPUTT)
```
[10:00] Segment duration limit reached: 1 day, 0:00:15
[10:00] Rotating segment for stream 348
[10:00] ERROR - ProcessLookupError
❌ Kein neues Segment gestartet
❌ Stream stuck forever
❌ Keine Post-Processing
```

### Nachher (GEFIXT)
```
[10:00] Segment duration limit reached: 1 day, 0:00:15
[10:00] Rotating segment for stream 348
[10:00] 🔄 ROTATION: Process already terminated externally, continuing
[10:00] Removed process stream_348 from tracking
[10:00] ✅ Successfully rotated to segment 002 for stream 348
✅ Neues Segment läuft
✅ Bei Stream-Ende: Post-Processing wird getriggert
```

---

## 🔧 Deployment Actions

### 1. Vor Deployment
```bash
# Backup Database
pg_dump streamvault > backup_$(date +%Y%m%d_%H%M%S).sql

# Stuck Recordings dokumentieren
psql streamvault -c "SELECT id, stream_id, start_time FROM recordings WHERE status = 'recording' AND start_time < NOW() - INTERVAL '24 hours';"
```

### 2. Nach Deployment
```bash
# Clean up stuck recordings (von vor dem Fix)
curl -X POST "http://localhost:8000/admin/recordings/cleanup-process-orphaned?dry_run=false"

# Monitor logs
tail -f logs/streamvault.log | grep "🔄 ROTATION\|✅ Successfully rotated"

# Verify segment files
ls -lh /recordings/*/stream_*_segments/
```

### 3. Validation
```bash
# Check für erfolgreiche Rotations
grep "Successfully rotated to segment" logs/streamvault.log.2025-11-* | wc -l

# Verify keine ProcessLookupError mehr
grep "ProcessLookupError" logs/streamvault.log.2025-11-* | wc -l
```

---

## 📚 Dokumentation

### Neue Dateien
- **`docs/segment_rotation_fixes.md`** - Komplette Bug-Analyse & Fix-Details
- **Backend Instructions erweitert** - Process Lifecycle Management Patterns

### Pattern Updates
- **Fail-Forward Strategy** - Continue auch wenn Cleanup fehlschlägt
- **Finally Blocks** - IMMER für kritisches Cleanup verwenden
- **uvloop Zombie Handling** - poll() vor returncode-Check
- **Expected vs Unexpected Exceptions** - Richtige Log-Levels

---

## ✅ Success Criteria

- [x] ProcessLookupError gefixt in `_rotate_segment()`
- [x] Type Hints korrigiert (`Optional[int]` für nullable params)
- [x] Comprehensive documentation erstellt
- [x] Backend instructions updated mit neuen Patterns
- [x] Empty Season directories werden jetzt auch gelöscht
- [ ] Deployment durchgeführt
- [ ] Stuck recordings cleaned up
- [ ] Neue Rotations erfolgreich (24h Monitor)
- [ ] Post-Processing läuft wieder für lange Streams

---

## 🗂️ Bonus Fix: Empty Season Directories

**Problem**: Cleanup löscht Streams, aber Season-Ordner bleiben übrig mit:
- `poster.jpg`, `fanart.jpg`, `banner.jpg` (Metadata)
- 0-Byte Symlinks
- Keine eigentlichen Stream-Dateien mehr

**Beispiel**:
```
/CohhCarnage/
├── Season 2025-09/          ← Bleibt stehen trotz gelöschter Streams!
│   ├── poster.jpg           ← 166 KB
│   ├── fanart.jpg           ← 67 KB
│   ├── CohhCarnage - ... (Symlink 0b)
```

**Lösung**:
Nach dem Löschen eines Episode-Directories wird jetzt **auch** das Season-Directory geprüft:

```python
# Episode-Ordner löschen
shutil.rmtree(recording_dir)

# Season-Ordner prüfen
season_dir = os.path.dirname(recording_dir)

# Löschen wenn:
# 1. Keine Subdirectories mehr (alle Episodes weg)
# 2. Nur Metadata-Files übrig (poster.jpg, fanart.jpg, etc.)

if no_subdirs and only_metadata:
    shutil.rmtree(season_dir)
    logger.info(f"🗂️ Removed empty Season directory: {season_dir}")
```

**Eligible für Löschung**:
- Ordner ohne Subdirectories
- Nur Files: `poster.jpg`, `fanart.jpg`, `season-poster.jpg`, `banner.jpg`
- 0-Byte Symlinks werden ignoriert (beim Size-Check)

---

## 🎯 Lesson Learned

**"Fail Forward, Not Backward"**

Wenn ein Cleanup-Step fehlschlägt:
- ❌ NICHT: Return/Abort → blockiert System
- ✅ SONDERN: Log + Continue → System läuft weiter

**External Processes sind unzuverlässig** - immer annehmen dass sie jederzeit sterben können:
- OOM Killer
- Container Restarts  
- Network Failures
- Application Crashes

**Finally Blocks für kritisches Cleanup** - vor allem bei:
- Process/Resource Tracking Dictionaries
- Locks/Semaphores
- File Handles
- Network Connections

---

**Fix Applied**: 2025-11-09  
**Testing Required**: 24h monitoring after deployment  
**Affected Code**: `app/services/recording/process_manager.py::_rotate_segment()`

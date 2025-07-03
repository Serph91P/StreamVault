# StreamVault Remux Fixes - Analyse und Lösung

## Identifizierte Probleme

### 1. AAC Bitstream Format Fehler
**Problem:** FFmpeg-Logs zeigen:
```
[mp4 @ 0x...] Malformed AAC bitstream detected: use the audio bitstream filter 'aac_adtstoasc' to fix it
```

**Ursache:** Twitch-Streams verwenden ADTS AAC Format, das nicht direkt in MP4-Container kompatibel ist.

**Lösung:** `-bsf:a aac_adtstoasc` Filter zu allen Remux-Befehlen hinzugefügt.

### 2. "Operation not permitted" Fehler
**Problem:** FFmpeg beendet sich mit:
```
av_interleaved_write_frame(): Operation not permitted
Error writing trailer: Operation not permitted
```

**Ursache:** Datei-Permissions oder parallele Zugriffe auf die Ausgabedatei.

**Lösung:** 
- Ausgabeverzeichnis-Permissions explizit setzen (0o755)
- Existierende MP4-Dateien vor Remux entfernen
- Bessere Fehlerbehandlung implementiert

### 3. Deprecated FFmpeg Parameter
**Problem:** `-vsync` ist deprecated und zeigt Warnungen.

**Lösung:** Ersetzt durch `-fps_mode`.

## Implementierte Fixes

### 1. Hauptfunktion `_remux_to_mp4_with_logging`
- ✅ `-bsf:a aac_adtstoasc` hinzugefügt
- ✅ `-fps_mode` statt `-vsync`
- ✅ Directory-Permissions und Cleanup

### 2. Fallback-Funktion `_remux_to_mp4_fallback`
- ✅ `-bsf:a aac_adtstoasc` hinzugefügt
- ✅ `-fps_mode` statt `-vsync`

### 3. Two-Step-Fallback `_remux_to_mp4_two_step`
- ✅ `-bsf:a aac_adtstoasc` für finale Kombination
- ✅ Directory-Permissions

### 4. Erweiterte Fehlerbehandlung
- ✅ Spezifische Erkennung von "Operation not permitted"
- ✅ Spezifische Erkennung von "Malformed AAC bitstream"
- ✅ Automatisches Fallback zu nächster Methode

## Warum die Aufnahmen verkürzt waren

Die Aufnahmen wurden korrekt von Streamlink aufgezeichnet (vollständige .ts Dateien), aber:

1. **AAC-Format-Problem:** Der `aac_adtstoasc` Filter fehlte, sodass FFmpeg die Audio-Streams nicht korrekt in den MP4-Container einbetten konnte.

2. **Permission-Fehler:** "Operation not permitted" führte zum vorzeitigen Abbruch des Remux-Prozesses.

3. **Resultat:** Nur die ersten paar Frames/Sekunden wurden in die MP4-Datei geschrieben, bevor FFmpeg mit einem Fehler abbricht.

Die .ts Dateien enthielten die vollständigen Aufnahmen, aber der Remux-Prozess konnte sie nicht vollständig konvertieren.

## Erwartete Verbesserungen

Nach den Fixes sollten:
- ✅ Vollständige MP4-Dateien erstellt werden
- ✅ Kein AAC-Bitstream-Fehler mehr auftreten
- ✅ Keine "Operation not permitted" Fehler
- ✅ Automatische Fallback-Methoden bei Problemen
- ✅ Bessere Logging für Debugging

## Test-Empfehlung

1. Eine neue Aufnahme starten
2. Log-Dateien in `/logs/ffmpeg/` überwachen
3. Überprüfen, dass keine AAC-Bitstream-Fehler auftreten
4. Validieren, dass MP4-Dateien vollständige Dauer haben

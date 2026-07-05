# StreamVault Analysebericht

## 1. Kurzüberblick
StreamVault ist eine FastAPI Anwendung mit Vue Frontend zur automatischen Twitch Aufnahme. Der zentrale Pfad ist EventSub oder manueller Start, Streamlink Prozess, segmentierte TS Aufnahme, Post Processing, Metadaten, Queue und WebSocket Status.

## 2. Erkannte Kernservices
- `app/main.py`: FastAPI Lifespan, Migrationen, EventSub, Hintergrunddienste, Shutdown.
- `RecordingService`: Kompatibilitätsfassade, delegiert auf den Orchestrator.
- `RecordingOrchestrator`: zentraler Einstieg in Recording, Recovery, Status und Post Processing.
- `RecordingLifecycleManager`: Start, Stop, Duplicate Prevention, Monitoring und Shutdown.
- `ProcessManager`: Streamlink Subprocesses, Segmentierung, Rotation und Prozessbeendigung.
- `RecordingStateManager`: In Memory Status, aktive Tasks, Wiederherstellung aus Persistenz.
- `StatePersistenceService`: `active_recordings_state`, Heartbeats, Stale Cleanup, Recovery Basis.
- `startup_init.cleanup_zombie_recordings`: Recovery Logik beim Neustart.
- `BackgroundQueueService` und Queue Manager: Post Processing, Cleanup, Recovery Tasks.

## 3. Kritische Pfade
- Start: EventSub oder manuell erstellt Stream und Recording, danach Streamlink Prozess und persistenter Active State.
- Laufzeit: ProcessManager hält Prozess und Segmentstatus, StatePersistenceService hält Heartbeats frisch.
- Stop: RecordingLifecycleManager beendet Prozess, plant Post Processing und entfernt aktiven State.
- Neustart: Startup Init sucht Recording Status `recording`, prüft Twitch Live Status, nimmt wieder auf oder beendet.
- Shutdown: `app/main.py` ruft Recording Shutdown zuerst auf, danach Live Streaming, WebSocket, Queue und DB Dispose.

## 4. Recording Flow
1. API oder EventSub ruft `RecordingService.start_recording`.
2. `RecordingLifecycleManager.start_recording` validiert Stream und blockiert Duplikate.
3. DB Recording wird erstellt.
4. `ProcessManager.start_recording_process` erzeugt segmentierte Ausgabe und startet Streamlink.
5. Aktive Recording Daten liegen in Memory und Persistenz.
6. Monitor wartet auf Prozessende, aktualisiert Status und stößt Post Processing an.

## 5. Resume und Recovery Flow
- Persistenter State liegt in `active_recordings_state`.
- `StatePersistenceService` prüft Prozess PIDs und Heartbeats.
- `cleanup_zombie_recordings` entscheidet beim Startup anhand Twitch API Status, ob eine Aufnahme wieder aufgenommen wird.
- `resume_segments_dir` verhindert, dass Resume Segmente in einem neuen Ordner landen.

## 6. Risiken und technische Schulden
- Recovery ist stark von Live Status API abhängig. Bei Netzfehlern wird aktuell konservativ offline angenommen, was laufende Aufnahmen zu früh stoppen kann.
- `StatePersistenceService._process_exists` gibt ohne psutil immer False zurück. Das schwächt Fallbacks und Tests.
- `ProcessManager` setzt `psutil_available=True`, ohne psutil wirklich zu importieren. Das ist irreführend und macht Monitoring Semantik fragil.
- State liegt parallel in DB, Memory und ProcessManager. Das ist funktional, aber crashanfällig bei nicht atomaren Zwischenzuständen.
- Viele breite `except Exception` Pfade loggen nur und laufen weiter. Das ist für Service Verfügbarkeit nützlich, verdeckt aber manche Recovery Fehler.
- Es gibt Backward Compatibility Wrapper und alte Migrations Backups. Löschung ist riskant ohne Call Site Prüfung.

## 7. Konkreter Umsetzungsplan
1. Analyse dokumentieren und Kanban Tasks anlegen.
2. Prozess Existenzprüfung in `StatePersistenceService` robuster machen, inklusive OS Fallback ohne psutil.
3. Startup Recovery bei Twitch API Fehlern ausfallsicherer machen, ohne Kernfunktionalität zu ändern.
4. ProcessManager psutil Verfügbarkeit korrekt erkennen.
5. Regressionstests für die neuen Robustheitsfälle ergänzen.
6. Lokale Checks ausführen, Diff prüfen, Commit erstellen.

## 8. Nicht angefasst ohne weiteren Nachweis
- Keine großflächige Service Zerlegung.
- Keine Löschung alter Migrations Backups.
- Keine Änderung der Kernlogik von Streamlink Kommandoaufbau oder Post Processing Pipeline.

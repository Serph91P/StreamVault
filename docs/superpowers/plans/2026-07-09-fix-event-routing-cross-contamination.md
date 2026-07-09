# Fix: Falsche Streamer-Events in MP4-Bookmarks (Event-Routing) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `channel.update`-Events (Chapter-/Bookmark-Marker) dürfen nie mehr am falschen Stream landen; fertige MP4s bekommen nur noch Chapters des tatsächlich aufgenommenen Streams.

**Architecture:** Die Fehlerkette wird an allen Gliedern gefixt: (1) EventSub-Deduplizierung zentral im Webhook per `Twitch-Eventsub-Message-Id` (aktuell 100 % wirkungslos, weil `_is_duplicate_event` das volle Payload erwartet, aber nur das flache Event bekommt), (2) `handle_stream_online` dedupliziert per `twitch_stream_id` und schließt verwaiste offene Streams, (3) `handle_stream_update` hängt Events an den Stream mit aktiver Aufnahme statt an den „neuesten offenen Stream" und bekommt den Scoping-Bug (`if stream:` außerhalb `if streamer:`) gefixt, (4) `handle_stream_offline` schließt ALLE offenen Streams, (5) `ensure_all_chapter_formats` bekommt denselben Cross-Contamination-Guard wie die Schwesterfunktionen.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy (sync), pytest + pytest-asyncio (Tests laufen synchron via `asyncio.run`), SQLite in-memory für Tests.

**Root-Cause-Referenzen:**
- `app/main.py:989-998` — Webhook übergibt nur `body_json["event"]` an Handler.
- `app/events/handler_registry.py:162-191` — `_is_duplicate_event` liest `data["id"]`/`data["event"]`/`data["subscription"]` → existieren im flachen Event nicht → immer `False`.
- `app/events/handler_registry.py:220-231` — `stream.online` legt bedingungslos neuen `Stream` an (kein Dedup per `twitch_stream_id`).
- `app/events/handler_registry.py:499-505` — `channel.update` → „neuester offener Stream" statt aufgenommener Stream.
- `app/events/handler_registry.py:507` — `if stream:` außerhalb `if streamer:` (UnboundLocalError bei unbekanntem Broadcaster).
- `app/events/handler_registry.py:349-357` — offline schließt nur einen Stream.
- `app/services/media/metadata_service.py:1789ff` — `ensure_all_chapter_formats` ohne Guard (vgl. Guard in `generate_metadata_for_stream` Z. 420-439).

**Verifikation lokal (einmalig pro Session):**
```bash
cd "C:/Users/max.ebert/Documents/private/StreamVault/.claude/worktrees/streamvault-event-routing-c2f99c"
python -m venv .venv-test 2>/dev/null || true
.venv-test/Scripts/python -m pip install -q -r requirements.txt pytest pytest-asyncio httpx
```
Testlauf immer mit: `.venv-test/Scripts/python -m pytest tests/... -v --tb=short`

---

## File Structure

- Modify: `app/events/handler_registry.py` — Dedup-Methode ersetzen, 3 Handler fixen, Helper `_resolve_event_target_stream` neu.
- Modify: `app/main.py` — Dedup-Aufruf im Notification-Branch des Webhooks.
- Modify: `app/services/media/metadata_service.py` — Guard in `ensure_all_chapter_formats`.
- Create: `tests/test_eventsub_event_routing.py` — alle neuen Tests (ein File, ein Thema: Event-Routing).

Test-Gemeinsamkeiten (ganz oben in `tests/test_eventsub_event_routing.py`, wird in Task 1 angelegt, alle späteren Tasks hängen Tests in dieses File an):

```python
"""Tests for EventSub event routing: dedup, stream dedup, event→stream mapping.

Regression tests for the bug where channel.update events (chapter markers)
were attached to the wrong stream and ended up as bookmarks in the wrong MP4.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database import Base, SessionLocal, engine
from app.models import Recording, Stream, Streamer, StreamEvent


def _make_registry():
    """Build an EventHandlerRegistry with all heavy dependencies mocked."""
    with patch("app.events.handler_registry.RecordingService"), patch(
        "app.events.handler_registry.ConfigManager"
    ), patch("app.events.handler_registry.NotificationService"):
        from app.events.handler_registry import EventHandlerRegistry

        registry = EventHandlerRegistry(connection_manager=MagicMock())
    registry.notification_service = AsyncMock()
    registry.recording_service = AsyncMock()
    registry.config_manager = MagicMock()
    registry.config_manager.is_recording_enabled.return_value = False
    registry.get_user_info = AsyncMock(return_value=None)
    return registry


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        # Clean relevant tables so tests are independent
        session.query(StreamEvent).delete()
        session.query(Recording).delete()
        session.query(Stream).delete()
        session.query(Streamer).delete()
        session.commit()
        yield session
    finally:
        session.close()


def _make_streamer(session, twitch_id="111", username="streamer_a"):
    streamer = Streamer(
        twitch_id=twitch_id,
        username=username,
        is_live=False,
    )
    session.add(streamer)
    session.commit()
    return streamer
```

**Hinweis für den Implementierer:** Falls das `Streamer`-Model Pflichtfelder hat, die hier fehlen (prüfen in `app/models.py`), diese mit Dummy-Werten ergänzen. Tests laufen im selben Thread wie `asyncio.run(...)`, dadurch teilt die In-Memory-SQLite-DB die Connection (SingletonThreadPool).

---

### Task 1: Zentrale EventSub-Deduplizierung per Message-ID

**Files:**
- Modify: `app/events/handler_registry.py:162-191` (Methode ersetzen), `:198-202`, `:330-334`, `:448-450` (Aufrufe entfernen)
- Modify: `app/main.py:983-998`
- Create: `tests/test_eventsub_event_routing.py`

- [ ] **Step 1: Testdatei mit Header (siehe „File Structure") anlegen und failing Tests schreiben**

```python
class TestIsDuplicateMessage:
    def test_same_message_id_is_duplicate(self):
        registry = _make_registry()
        assert registry.is_duplicate_message("msg-1", "channel.update", "111") is False
        assert registry.is_duplicate_message("msg-1", "channel.update", "111") is True

    def test_different_message_ids_are_not_duplicates(self):
        registry = _make_registry()
        assert registry.is_duplicate_message("msg-1", "stream.online", "111") is False
        assert registry.is_duplicate_message("msg-2", "stream.online", "111") is False

    def test_missing_message_id_never_dedups(self):
        registry = _make_registry()
        assert registry.is_duplicate_message("", "stream.online", "111") is False
        assert registry.is_duplicate_message(None, "stream.online", "111") is False

    def test_old_broken_method_is_gone(self):
        registry = _make_registry()
        assert not hasattr(registry, "_is_duplicate_event")
```

- [ ] **Step 2: Tests laufen lassen — müssen failen**

Run: `.venv-test/Scripts/python -m pytest tests/test_eventsub_event_routing.py -v --tb=short`
Expected: FAIL (`AttributeError: ... has no attribute 'is_duplicate_message'`)

- [ ] **Step 3: `_is_duplicate_event` in `app/events/handler_registry.py` durch `is_duplicate_message` ersetzen**

Die komplette Methode `_is_duplicate_event` (Z. 162-191) löschen und ersetzen durch:

```python
    def is_duplicate_message(
        self,
        message_id: Optional[str],
        event_type: Optional[str],
        broadcaster_id: Optional[str],
    ) -> bool:
        """Deduplicate EventSub deliveries by Twitch message id.

        Twitch retries notifications that are not acknowledged with a 2xx in
        time; every retry reuses the same Twitch-Eventsub-Message-Id header.
        Must be called from the webhook endpoint BEFORE dispatching to a
        handler (handlers only receive the flat event payload, which does not
        contain the message id).
        """
        try:
            if not message_id:
                return False

            event_fingerprint = f"{message_id}:{event_type}:{broadcaster_id}"

            # TTLCache automatically handles expiration - no manual cleanup needed!
            if event_fingerprint in self._processed_events:
                logger.info(
                    f"Ignoring duplicate EventSub delivery: {event_type} for "
                    f"broadcaster {broadcaster_id} (message_id={message_id})"
                )
                return True

            self._processed_events[event_fingerprint] = datetime.now()
            return False

        except Exception as e:
            logger.error(f"Error checking for duplicate event: {e}", exc_info=True)
            return False
```

- [ ] **Step 4: Die drei toten Aufrufe in den Handlern entfernen**

In `handle_stream_online` (Z. 198-202) diesen Block löschen:
```python
        if self._is_duplicate_event(data):
            logger.info(
                f"🎬 DUPLICATE_STREAM_ONLINE_EVENT: Skipping duplicate event for {data.get('broadcaster_user_name')}"
            )
            return
```
In `handle_stream_offline` (Z. 329-334) diesen Block löschen:
```python
        # Event-Deduplizierung
        if self._is_duplicate_event(data):
            logger.info(
                f"🎬 DUPLICATE_STREAM_OFFLINE_EVENT: Skipping duplicate event for {data.get('broadcaster_user_name')}"
            )
            return
```
In `handle_stream_update` (Z. 448-450) diesen Block löschen:
```python
        # Event-Deduplizierung
        if self._is_duplicate_event(data):
            return
```
Danach mit Grep prüfen, dass es keine weiteren Verwendungen gibt: `grep -rn "_is_duplicate_event" app/`

- [ ] **Step 5: Dedup-Aufruf in `app/main.py` einbauen**

Im Notification-Branch (Z. 983-998), direkt nach `event_data = body_json.get("event")` einfügen:

```python
                if event_registry.is_duplicate_message(
                    message_id,
                    event_type,
                    (event_data or {}).get("broadcaster_user_id"),
                ):
                    logger.info(
                        f"Duplicate EventSub delivery ignored: {event_type} "
                        f"(message_id={message_id})"
                    )
                    return Response(status_code=204)
```

(`message_id` existiert bereits als Variable aus Z. 913.)

- [ ] **Step 6: Tests laufen lassen — müssen passen**

Run: `.venv-test/Scripts/python -m pytest tests/test_eventsub_event_routing.py -v --tb=short`
Expected: 4 PASS

- [ ] **Step 7: Commit**

```bash
git add app/events/handler_registry.py app/main.py tests/test_eventsub_event_routing.py
git commit -m "fix(eventsub): dedup deliveries by Twitch message id at the webhook

_is_duplicate_event expected the full EventSub payload but handlers only
receive the flat event object, so it always returned False and Twitch
redeliveries were processed multiple times."
```

---

### Task 2: `handle_stream_online` — Dedup per `twitch_stream_id` + verwaiste Streams schließen

**Files:**
- Modify: `app/events/handler_registry.py` (`handle_stream_online`, nach dem `if streamer:` in Z. ~214)
- Test: `tests/test_eventsub_event_routing.py`

- [ ] **Step 1: Failing Tests anhängen**

```python
class TestHandleStreamOnline:
    def _online_payload(self, twitch_stream_id="9001", broadcaster_id="111"):
        return {
            "id": twitch_stream_id,
            "broadcaster_user_id": broadcaster_id,
            "broadcaster_user_name": "streamer_a",
            "broadcaster_user_login": "streamer_a",
            "started_at": "2026-07-09T12:00:00Z",
        }

    def test_duplicate_online_does_not_create_second_stream(self, db):
        streamer = _make_streamer(db)
        registry = _make_registry()

        asyncio.run(registry.handle_stream_online(self._online_payload()))
        asyncio.run(registry.handle_stream_online(self._online_payload()))

        streams = db.query(Stream).filter(Stream.streamer_id == streamer.id).all()
        assert len(streams) == 1

    def test_new_online_closes_stale_open_streams(self, db):
        streamer = _make_streamer(db)
        stale = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc),
            twitch_stream_id="8000",
        )
        db.add(stale)
        db.commit()
        stale_id = stale.id

        registry = _make_registry()
        asyncio.run(registry.handle_stream_online(self._online_payload()))

        db.expire_all()
        stale_row = db.query(Stream).filter(Stream.id == stale_id).first()
        assert stale_row.ended_at is not None

        new_stream = (
            db.query(Stream).filter(Stream.twitch_stream_id == "9001").first()
        )
        assert new_stream is not None
        assert new_stream.ended_at is None
```

- [ ] **Step 2: Tests laufen lassen — müssen failen**

Run: `.venv-test/Scripts/python -m pytest tests/test_eventsub_event_routing.py::TestHandleStreamOnline -v --tb=short`
Expected: FAIL (`len(streams) == 2` bzw. `stale_row.ended_at is None`)

- [ ] **Step 3: Implementieren**

In `handle_stream_online`, innerhalb `if streamer:` (nach dem Setzen von `profile_image_url`/`description`, vor `stream = Stream(...)`) einfügen:

```python
                    # Deduplicate: Twitch redelivers stream.online when we do
                    # not ACK in time. A second Stream row would leave duplicate
                    # un-ended streams and mis-route channel.update chapter
                    # events to the wrong recording.
                    existing_stream = (
                        db.query(Stream)
                        .filter(Stream.twitch_stream_id == data["id"])
                        .first()
                    )
                    if existing_stream:
                        logger.info(
                            f"🎬 STREAM_ALREADY_KNOWN: twitch_stream_id={data['id']} "
                            f"already mapped to stream_id={existing_stream.id}; "
                            "skipping duplicate stream.online event"
                        )
                        return

                    started_at = datetime.fromisoformat(
                        data["started_at"].replace("Z", "+00:00")
                    )

                    # Close any stale still-open streams for this streamer so
                    # channel.update events can never attach to an old session.
                    stale_streams = (
                        db.query(Stream)
                        .filter(Stream.streamer_id == streamer.id)
                        .filter(Stream.ended_at.is_(None))
                        .all()
                    )
                    for stale_stream in stale_streams:
                        logger.warning(
                            f"🧹 CLOSING_STALE_STREAM: stream_id={stale_stream.id} "
                            f"(twitch_stream_id={stale_stream.twitch_stream_id}) was "
                            "still open when a new stream started"
                        )
                        stale_stream.ended_at = started_at
```

Danach in der bestehenden `Stream(...)`-Erzeugung und dem `initial_event`/`pre_stream_event` die beiden `datetime.fromisoformat(data["started_at"].replace("Z", "+00:00"))`-Ausdrücke durch die neue Variable `started_at` ersetzen (DRY).

- [ ] **Step 4: Tests laufen lassen — müssen passen**

Run: `.venv-test/Scripts/python -m pytest tests/test_eventsub_event_routing.py -v --tb=short`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add app/events/handler_registry.py tests/test_eventsub_event_routing.py
git commit -m "fix(eventsub): dedup stream.online by twitch_stream_id and close stale open streams

Duplicate stream.online deliveries created multiple un-ended Stream rows
per streamer; channel.update chapter events then attached to whichever
row sorted newest, corrupting the finished MP4's bookmarks."
```

---

### Task 3: `handle_stream_update` — Events an den aufgenommenen Stream + Scoping-Fix

**Files:**
- Modify: `app/events/handler_registry.py` (`handle_stream_update` Z. 447-652, neuer Helper davor)
- Test: `tests/test_eventsub_event_routing.py`

- [ ] **Step 1: Failing Tests anhängen**

```python
class TestHandleStreamUpdate:
    def _update_payload(self, broadcaster_id="111"):
        return {
            "broadcaster_user_id": broadcaster_id,
            "broadcaster_user_login": "streamer_a",
            "title": "New Title",
            "category_name": "New Game",
            "language": "de",
        }

    def test_event_attaches_to_actively_recorded_stream(self, db):
        """Two open streams; the OLDER one has the active recording.

        The chapter marker must go to the recorded stream, not the newest."""
        streamer = _make_streamer(db)
        recorded = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
            twitch_stream_id="8000",
        )
        orphan = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 9, 11, 0, tzinfo=timezone.utc),
            twitch_stream_id="9001",
        )
        db.add_all([recorded, orphan])
        db.commit()
        db.add(
            Recording(
                stream_id=recorded.id,
                status="recording",
                start_time=datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
            )
        )
        db.commit()

        registry = _make_registry()
        asyncio.run(registry.handle_stream_update(self._update_payload()))

        events = db.query(StreamEvent).filter(
            StreamEvent.event_type == "channel.update"
        ).all()
        assert len(events) == 1
        assert events[0].stream_id == recorded.id

    def test_fallback_to_latest_open_stream_without_recording(self, db):
        streamer = _make_streamer(db)
        older = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
            twitch_stream_id="8000",
        )
        newer = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 9, 11, 0, tzinfo=timezone.utc),
            twitch_stream_id="9001",
        )
        db.add_all([older, newer])
        db.commit()

        registry = _make_registry()
        asyncio.run(registry.handle_stream_update(self._update_payload()))

        events = db.query(StreamEvent).filter(
            StreamEvent.event_type == "channel.update"
        ).all()
        assert len(events) == 1
        assert events[0].stream_id == newer.id

    def test_unknown_broadcaster_is_ignored_without_error(self, db):
        registry = _make_registry()
        # Must not raise (previously: UnboundLocalError on `stream`)
        asyncio.run(registry.handle_stream_update(self._update_payload("999")))
        assert db.query(StreamEvent).count() == 0
```

**Hinweis:** Pflichtfelder des `Recording`-Models in `app/models.py` prüfen und ggf. im Test ergänzen (z. B. `path`).

- [ ] **Step 2: Tests laufen lassen — müssen failen**

Run: `.venv-test/Scripts/python -m pytest tests/test_eventsub_event_routing.py::TestHandleStreamUpdate -v --tb=short`
Expected: Test 1 FAIL (Event landet auf `orphan`), Test 3 evtl. FAIL

- [ ] **Step 3: Helper einfügen (direkt vor `handle_stream_update`)**

```python
    def _resolve_event_target_stream(
        self, db: Session, streamer_id: int
    ) -> Optional[Stream]:
        """Resolve which stream a channel.update event belongs to.

        Prefer the stream that is actively being recorded — its StreamEvents
        become the chapter markers of the finished MP4. Fall back to the most
        recent still-open stream when no recording is active.
        """
        stream = (
            db.query(Stream)
            .join(Recording, Recording.stream_id == Stream.id)
            .filter(Stream.streamer_id == streamer_id)
            .filter(Recording.status == "recording")
            # A stream being actively recorded must still be open; stuck
            # status="recording" rows on ended streams (zombie recordings)
            # must not steal chapter events.
            .filter(Stream.ended_at.is_(None))
            .order_by(Stream.started_at.desc())
            .first()
        )
        if stream:
            return stream

        return (
            db.query(Stream)
            .filter(Stream.streamer_id == streamer_id)
            .filter(Stream.ended_at.is_(None))
            .order_by(Stream.started_at.desc())
            .first()
        )
```

`Session` für den Type-Hint importieren: oben `from sqlalchemy.orm import Session` ergänzen (prüfen, ob schon vorhanden).

- [ ] **Step 4: `handle_stream_update` restrukturieren**

Kompletten Body (Z. 452-652) so umbauen — Early-Return statt verschachteltem `if streamer:`; alles Folgende bleibt inhaltlich identisch, rückt aber korrekt unter den Guard:

```python
    async def handle_stream_update(self, data: dict):
        try:
            logger.debug(f"Processing stream update event: {data}")
            with SessionLocal() as db:
                streamer = (
                    db.query(Streamer)
                    .filter(Streamer.twitch_id == data["broadcaster_user_id"])
                    .first()
                )

                if not streamer:
                    logger.warning(
                        "channel.update for unknown broadcaster "
                        f"{data.get('broadcaster_user_id')}; ignoring"
                    )
                    return

                logger.debug(
                    f"Found streamer: {streamer.username} (ID: {streamer.id})"
                )
                # ... (bestehender Code: effective_category_name-Auflösung,
                #      streamer.title/category/language-Update, db.commit())

                stream = self._resolve_event_target_stream(db, streamer.id)

                if stream:
                    # ... (bestehender Code: stream.title/category/language
                    #      aktualisieren, StreamEvent anlegen, db.commit())
                else:
                    logger.info(
                        f"Streamer {streamer.username} is offline, storing update for future use"
                    )

                # ... (bestehender Code: Notification, Category-Pflege,
                #      Favorite-Category-Notifications — unverändert,
                #      jetzt sauber innerhalb des Streamer-Scopes)
        except SQLAlchemyError as e:
            logger.error(f"Database error handling stream update event: {e}")
        except Exception as e:
            logger.error(f"Error handling stream update event: {e}", exc_info=True)
```

Wichtig: Der bestehende Code der Blöcke wird NICHT verändert, nur (a) der Streamer-Guard wird zum Early-Return, (b) die Stream-Query (Z. 499-505) wird durch `self._resolve_event_target_stream(db, streamer.id)` ersetzt, (c) alle nachfolgenden Blöcke (Z. 507-648) rücken auf das Indent-Level innerhalb `with SessionLocal() as db:`.

- [ ] **Step 5: Tests laufen lassen — müssen passen**

Run: `.venv-test/Scripts/python -m pytest tests/test_eventsub_event_routing.py -v --tb=short`
Expected: alle PASS

- [ ] **Step 6: Commit**

```bash
git add app/events/handler_registry.py tests/test_eventsub_event_routing.py
git commit -m "fix(eventsub): attach channel.update events to the actively recorded stream

channel.update events (chapter markers) were attached to the newest
un-ended stream of the streamer. With duplicate/orphaned open streams
this routed chapters to the wrong stream and thus into the wrong MP4.
Also fixes the scoping bug where 'if stream:' sat outside 'if streamer:'
causing UnboundLocalError for unknown broadcasters."
```

---

### Task 4: `handle_stream_offline` — alle offenen Streams schließen

**Files:**
- Modify: `app/events/handler_registry.py` (`handle_stream_offline` Z. 349-366)
- Test: `tests/test_eventsub_event_routing.py`

- [ ] **Step 1: Failing Test anhängen**

```python
class TestHandleStreamOffline:
    def test_offline_closes_all_open_streams(self, db):
        streamer = _make_streamer(db)
        s1 = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
            twitch_stream_id="8000",
        )
        s2 = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 9, 11, 0, tzinfo=timezone.utc),
            twitch_stream_id="9001",
        )
        db.add_all([s1, s2])
        db.commit()

        registry = _make_registry()
        asyncio.run(
            registry.handle_stream_offline(
                {
                    "broadcaster_user_id": "111",
                    "broadcaster_user_name": "streamer_a",
                    "broadcaster_user_login": "streamer_a",
                }
            )
        )

        db.expire_all()
        open_streams = (
            db.query(Stream)
            .filter(Stream.streamer_id == streamer.id)
            .filter(Stream.ended_at.is_(None))
            .all()
        )
        assert open_streams == []
```

- [ ] **Step 2: Test laufen lassen — muss failen**

Run: `.venv-test/Scripts/python -m pytest tests/test_eventsub_event_routing.py::TestHandleStreamOffline -v --tb=short`
Expected: FAIL (ein Stream bleibt offen)

- [ ] **Step 3: Implementieren**

In `handle_stream_offline` den Block Z. 349-364 ersetzen. Vorher:

```python
                    stream = (
                        db.query(Stream)
                        .filter(Stream.streamer_id == streamer.id)
                        .filter(Stream.ended_at.is_(None))
                        .order_by(Stream.started_at.desc())
                        .first()
                    )
                    if stream:
                        stream.ended_at = datetime.now(timezone.utc)
                        ...
```

Nachher:

```python
                    open_streams = (
                        db.query(Stream)
                        .filter(Stream.streamer_id == streamer.id)
                        .filter(Stream.ended_at.is_(None))
                        .order_by(Stream.started_at.desc())
                        .all()
                    )
                    stream = open_streams[0] if open_streams else None
                    ended_at = datetime.now(timezone.utc)

                    # Close ALL open streams — leftover un-ended rows would
                    # attract future channel.update chapter events.
                    for open_stream in open_streams:
                        open_stream.ended_at = ended_at

                    if stream:
                        # Update last stream info on streamer for offline display
                        streamer.last_stream_title = stream.title
                        streamer.last_stream_category_name = stream.category_name
                        streamer.last_stream_ended_at = stream.ended_at
                        # Note: last_stream_viewer_count will be updated when recording finishes
                        # (not available in stream.offline event)
```

(Der Rest des Handlers — Notification, Recording-Stop — bleibt unverändert und nutzt weiterhin `stream`.)

- [ ] **Step 4: Tests laufen lassen — müssen passen**

Run: `.venv-test/Scripts/python -m pytest tests/test_eventsub_event_routing.py -v --tb=short`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add app/events/handler_registry.py tests/test_eventsub_event_routing.py
git commit -m "fix(eventsub): close all un-ended streams on stream.offline

Only the newest open stream was closed; older orphaned rows stayed
ended_at=NULL forever and kept attracting channel.update chapter events."
```

---

### Task 5: Cross-Contamination-Guard in `ensure_all_chapter_formats`

**Files:**
- Modify: `app/services/media/metadata_service.py` (`ensure_all_chapter_formats`, nach dem Stream-Lookup Z. ~1810-1815)
- Test: `tests/test_eventsub_event_routing.py`

- [ ] **Step 1: Failing Test anhängen**

```python
class TestChapterCrossContaminationGuard:
    def test_refuses_wrong_streamer_path(self, db, tmp_path):
        streamer = _make_streamer(db, twitch_id="222", username="streamer_a")
        stream = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
            twitch_stream_id="7000",
        )
        db.add(stream)
        db.commit()

        from app.services.media.metadata_service import MetadataService

        service = MetadataService()
        wrong_dir = tmp_path / "streamer_b" / "Season 2026-07"
        wrong_dir.mkdir(parents=True)
        mp4_path = wrong_dir / "episode.mp4"

        result = asyncio.run(
            service.ensure_all_chapter_formats(stream.id, str(mp4_path), db)
        )

        assert result is None
        assert list(wrong_dir.iterdir()) == [] or not any(
            p.suffix in {".vtt", ".srt", ".txt", ".xml"}
            for p in wrong_dir.iterdir()
        )

    def test_allows_correct_streamer_path(self, db, tmp_path):
        streamer = _make_streamer(db, twitch_id="333", username="streamer_c")
        stream = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
            twitch_stream_id="7001",
            title="My Stream",
            category_name="My Game",
        )
        db.add(stream)
        db.commit()

        from app.services.media.metadata_service import MetadataService

        service = MetadataService()
        right_dir = tmp_path / "streamer_c" / "Season 2026-07"
        right_dir.mkdir(parents=True)
        mp4_path = right_dir / "episode.mp4"

        result = asyncio.run(
            service.ensure_all_chapter_formats(stream.id, str(mp4_path), db)
        )

        assert result is not None
        assert (right_dir / "episode-ffmpeg-chapters.txt").exists()
```

- [ ] **Step 2: Tests laufen lassen — Test 1 muss failen, Test 2 sollte passen**

Run: `.venv-test/Scripts/python -m pytest tests/test_eventsub_event_routing.py::TestChapterCrossContaminationGuard -v --tb=short`
Expected: `test_refuses_wrong_streamer_path` FAIL (`result is not None`)

- [ ] **Step 3: Guard implementieren**

In `ensure_all_chapter_formats` direkt nach dem Stream-Lookup (`if not stream: ... return None`, Z. ~1810-1815) einfügen:

```python
                # Cross-contamination guard (mirrors generate_metadata_for_stream):
                # refuse to write chapter files when the target path does not
                # belong to this stream's streamer. Otherwise the wrong
                # streamer's events end up as bookmarks in the finished MP4.
                streamer = stream.streamer
                if (
                    streamer
                    and getattr(streamer, "username", None)
                    and streamer.username.lower() not in str(mp4_path).lower()
                ):
                    logger.error(
                        f"CRITICAL: Chapter generation refused: stream {stream_id} "
                        f"belongs to {streamer.username} but target path is {mp4_path}. "
                        "This indicates wrong stream-to-recording mapping."
                    )
                    return None
```

- [ ] **Step 4: Tests laufen lassen — müssen passen**

Run: `.venv-test/Scripts/python -m pytest tests/test_eventsub_event_routing.py -v --tb=short`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/media/metadata_service.py tests/test_eventsub_event_routing.py
git commit -m "fix(chapters): refuse chapter generation when stream/path streamer mismatch

ensure_all_chapter_formats was the only step in the chapter pipeline
without the cross-contamination guard its sibling metadata functions
already have; a wrong stream_id↔mp4_path pairing wrote another
streamer's events as chapters next to the video."
```

---

### Task 6: Volle Test-Suite + Abschluss

- [ ] **Step 1: Komplette Suite laufen lassen**

Run: `.venv-test/Scripts/python -m pytest tests/ -v --tb=short`
Expected: alle Tests PASS (keine Regressionen; bestehende Tests wie `test_recording_recovery_resilience.py` unberührt)

- [ ] **Step 2: Ruff-Lint (CI nutzt ruff — prüfen ob konfiguriert)**

Run: `.venv-test/Scripts/python -m pip install -q ruff && .venv-test/Scripts/python -m ruff check app/events/handler_registry.py app/main.py app/services/media/metadata_service.py tests/test_eventsub_event_routing.py`
Expected: keine neuen Fehler (vorbestehende Fehler in unveränderten Zeilen ignorieren)

- [ ] **Step 3: Plan-Dokument committen**

```bash
git add docs/superpowers/plans/2026-07-09-fix-event-routing-cross-contamination.md
git commit -m "docs: add event-routing fix implementation plan"
```

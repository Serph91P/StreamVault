"""
Async repositories for the Phase 2 persistence foundation.

Repositories talk to an ``AsyncSession`` and use ``select``-based queries.
Writes may ``add``/``flush`` but NEVER commit or rollback: the caller owns the
transaction boundary with ``async with session.begin()``.
"""

from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GlobalSettings, Recording, Streamer


class AsyncStreamerRepository:
    """Async data access for ``Streamer`` rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self, include_test_data: bool = False) -> Sequence[Streamer]:
        statement = select(Streamer)
        if not include_test_data:
            statement = statement.where(
                (Streamer.is_test_data.is_(False)) | (Streamer.is_test_data.is_(None))
            )
        statement = statement.order_by(Streamer.username)
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def get_by_id(self, streamer_id: int) -> Optional[Streamer]:
        result = await self._session.execute(
            select(Streamer).where(Streamer.id == streamer_id)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[Streamer]:
        result = await self._session.execute(
            select(Streamer).where(Streamer.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_twitch_id(self, twitch_id: str) -> Optional[Streamer]:
        result = await self._session.execute(
            select(Streamer).where(Streamer.twitch_id == twitch_id)
        )
        return result.scalar_one_or_none()

    async def create(self, **fields: Any) -> Streamer:
        """Add and flush a new streamer. The caller owns the transaction."""
        streamer = Streamer(**fields)
        self._session.add(streamer)
        await self._session.flush()
        return streamer

    async def update(self, streamer: Streamer, **fields: Any) -> Streamer:
        """Apply field updates and flush. The caller owns the transaction."""
        for key, value in fields.items():
            setattr(streamer, key, value)
        streamer.last_updated = datetime.now(timezone.utc)
        await self._session.flush()
        return streamer


class AsyncRecordingRepository:
    """Async data access for ``Recording`` rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, recording_id: int) -> Optional[Recording]:
        result = await self._session.execute(
            select(Recording).where(Recording.id == recording_id)
        )
        return result.scalar_one_or_none()

    async def list_for_stream(self, stream_id: int) -> Sequence[Recording]:
        result = await self._session.execute(
            select(Recording)
            .where(Recording.stream_id == stream_id)
            .order_by(Recording.start_time)
        )
        return result.scalars().all()

    async def list_active_for_streamer(self, streamer_id: int) -> Sequence[Recording]:
        from app.models import Stream

        result = await self._session.execute(
            select(Recording)
            .join(Stream, Stream.id == Recording.stream_id)
            .where(
                Stream.streamer_id == streamer_id,
                Recording.end_time.is_(None),
            )
        )
        return result.scalars().all()

    async def create(
        self,
        *,
        stream_id: int,
        start_time: datetime,
        status: str,
        **fields: Any,
    ) -> Recording:
        """Add and flush a new recording. The caller owns the transaction."""
        recording = Recording(
            stream_id=stream_id,
            start_time=start_time,
            status=status,
            **fields,
        )
        self._session.add(recording)
        await self._session.flush()
        return recording

    async def end(
        self,
        recording: Recording,
        *,
        ended_at: datetime,
        status: str = "completed",
        **fields: Any,
    ) -> Recording:
        """Mark a recording ended and flush. The caller owns the transaction."""
        recording.end_time = ended_at
        recording.status = status
        for key, value in fields.items():
            setattr(recording, key, value)
        if (
            fields.get("duration") is None
            and recording.start_time is not None
            and ended_at is not None
        ):
            recording.duration = max(
                0, int((ended_at - recording.start_time).total_seconds())
            )
        await self._session.flush()
        return recording


class AsyncGlobalSettingsRepository:
    """Async data access for the singleton ``GlobalSettings`` row."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_singleton(self) -> GlobalSettings:
        """Return the singleton settings row, creating a stub if absent.

        The caller owns the transaction; if the outer boundary rolls back the
        stub is not persisted.
        """
        result = await self._session.execute(
            select(GlobalSettings).order_by(GlobalSettings.id).limit(1)
        )
        settings = result.scalars().first()
        if settings is None:
            settings = GlobalSettings(id=1)
            self._session.add(settings)
            await self._session.flush()
            await self._session.refresh(settings)
        return settings

    async def update(self, settings: GlobalSettings, **fields: Any) -> GlobalSettings:
        """Apply field updates and flush. The caller owns the transaction."""
        for key, value in fields.items():
            setattr(settings, key, value)
        await self._session.flush()
        return settings

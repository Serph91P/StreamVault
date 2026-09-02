"""
Async database utilities for StreamVault.

The async engine and sessionmaker are owned by ``app.database.DatabaseLifecycle``
and therefore lazily constructed; these helpers are a thin compatibility
layer over that lifecycle.
"""

import asyncio
from typing import Any, List
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from app.database import database_lifecycle
from app.models import Stream, Streamer
import logging

logger = logging.getLogger("streamvault")


async def get_recent_streams(limit: int = 10) -> List[Stream]:
    """
    Get recent streams using async database session.

    Args:
        limit: Maximum number of streams to return

    Returns:
        List of recent Stream objects
    """
    async_session = get_async_session_maker()
    async with async_session() as session:
        try:
            # Get recent completed streams (those with recording_path or ended_at)
            # Also load the stream_metadata relationship for thumbnail_url access
            result = await session.execute(
                select(Stream)
                .options(selectinload(Stream.stream_metadata))
                .filter(
                    (Stream.ended_at.isnot(None)) | (Stream.recording_path.isnot(None))
                )
                .order_by(desc(Stream.started_at))
                .limit(limit)
            )
            streams = result.scalars().all()
            return list(streams)
        except Exception as e:
            logger.error(f"Error fetching recent streams: {e}")
            return []


def get_async_engine():
    """Get the lifecycle-owned async database engine (created lazily)"""
    return database_lifecycle.async_engine


def get_async_session_maker():
    """Get the lifecycle-owned async session maker (created lazily)"""
    return database_lifecycle.async_session_factory


def get_async_session():
    """Get an async database session that must be used in async context manager"""
    async_session_maker = get_async_session_maker()
    return async_session_maker()


async def get_all_streamers() -> List[Streamer]:
    """
    Get all streamers using the async repository.

    Returns:
        List of all Streamer objects
    """
    from app.services.core.async_repositories import AsyncStreamerRepository

    async_session = get_async_session_maker()
    async with async_session() as session:
        try:
            repository = AsyncStreamerRepository(session)
            streamers = await repository.get_all(include_test_data=True)
            return list(streamers)
        except Exception as e:
            logger.error(f"Error fetching streamers: {e}")
            return []


async def get_streamers_with_streams() -> List[Streamer]:
    """
    Get all streamers with their streams loaded using async database session.

    Returns:
        List of Streamer objects with streams relationship loaded
    """
    async_session = get_async_session_maker()
    async with async_session() as session:
        try:
            result = await session.execute(
                select(Streamer).options(selectinload(Streamer.streams))
            )
            streamers = result.scalars().all()
            return list(streamers)
        except Exception as e:
            logger.error(f"Error fetching streamers with streams: {e}")
            return []


async def batch_process_items(
    items: List[Any],
    batch_size: int = 10,
    max_concurrent: int = 3,
    sleep_duration: float = 0.1,
):
    """
    Process items in batches with concurrency control.

    Args:
        items: List of items to process
        batch_size: Number of items per batch
        max_concurrent: Maximum concurrent batch operations
        sleep_duration: Delay between batches to prevent system overload (seconds)

    Yields:
        Batches of items for processing
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        async with semaphore:
            yield batch
            # Small delay to prevent overwhelming the system
            await asyncio.sleep(sleep_duration)


async def run_in_thread_pool(func, *args, **kwargs):
    """
    Run a synchronous function in a thread pool to avoid blocking async context.

    Args:
        func: Synchronous function to run
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        Result of the function execution
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)

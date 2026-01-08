"""
Async database utilities for StreamVault
"""

import asyncio
from typing import List, Any
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.database import get_database_url
from app.models import Stream, Streamer
from urllib.parse import urlparse, urlunparse
import logging

logger = logging.getLogger("streamvault")

# Create async engine and session maker
_async_engine = None
_async_session_maker = None


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
                .filter((Stream.ended_at.isnot(None)) | (Stream.recording_path.isnot(None)))
                .order_by(desc(Stream.started_at))
                .limit(limit)
            )
            streams = result.scalars().all()
            return list(streams)
        except Exception as e:
            logger.error(f"Error fetching recent streams: {e}")
            return []


def get_async_engine():
    """Get or create async database engine"""
    global _async_engine
    if _async_engine is None:
        database_url = get_database_url()
        # Parse the database URL
        parsed_url = urlparse(database_url)

        # Update the scheme for async support
        if parsed_url.scheme == "sqlite":
            async_scheme = "sqlite+aiosqlite"
        elif parsed_url.scheme in ("postgresql", "postgresql+psycopg"):
            # Handle both postgresql and postgresql+psycopg schemes
            # Use psycopg async adapter instead of asyncpg since we're using psycopg3
            async_scheme = "postgresql+psycopg"
        else:
            raise ValueError(f"Unsupported database scheme: {parsed_url.scheme}")

        # Reconstruct the URL with the updated scheme
        async_url = urlunparse(parsed_url._replace(scheme=async_scheme))

        logger.debug(f"Creating async engine with scheme: {async_scheme}, database: {parsed_url.path}")
        logger.debug(f"Original URL scheme: {parsed_url.scheme} -> Async scheme: {async_scheme}")
        _async_engine = create_async_engine(async_url, echo=False)
    return _async_engine


def get_async_session_maker():
    """Get or create async session maker"""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(bind=get_async_engine(), class_=AsyncSession, expire_on_commit=False)
    return _async_session_maker


def get_async_session():
    """Get an async database session that must be used in async context manager"""
    async_session_maker = get_async_session_maker()
    return async_session_maker()


async def get_all_streamers() -> List[Streamer]:
    """
    Get all streamers using async database session.

    Returns:
        List of all Streamer objects
    """
    async_session = get_async_session_maker()
    async with async_session() as session:
        try:
            result = await session.execute(select(Streamer))
            streamers = result.scalars().all()
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
            result = await session.execute(select(Streamer).options(selectinload(Streamer.streams)))
            streamers = result.scalars().all()
            return list(streamers)
        except Exception as e:
            logger.error(f"Error fetching streamers with streams: {e}")
            return []


async def batch_process_items(
    items: List[Any], batch_size: int = 10, max_concurrent: int = 3, sleep_duration: float = 0.1
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

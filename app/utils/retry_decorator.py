"""
Centralized retry utility for handling transient errors across the application.
"""

import asyncio
import functools
import logging
import random
from typing import Any, Callable, List, Optional, Type

logger = logging.getLogger("streamvault")


class RetryableError(Exception):
    """Base class for errors that should trigger retries."""


class NonRetryableError(Exception):
    """Base class for errors that should NOT trigger retries."""


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_backoff: bool = True,
    jitter: bool = True,
    retry_on: Optional[List[Type[Exception]]] = None,
    stop_on: Optional[List[Type[Exception]]] = None,
    log_attempts: bool = True,
):
    """
    Decorator for adding retry logic to functions and methods.

    Args:
        max_attempts: Maximum number of attempts (including the first one)
        base_delay: Base delay in seconds between retries
        max_delay: Maximum delay in seconds between retries
        exponential_backoff: Whether to use exponential backoff
        jitter: Whether to add random jitter to delays
        retry_on: List of exception types that should trigger retries
        stop_on: List of exception types that should stop retries immediately
        log_attempts: Whether to log retry attempts
    """
    if retry_on is None:
        retry_on = [Exception]

    if stop_on is None:
        stop_on = [NonRetryableError]

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Check if this error should stop retries immediately
                    if any(isinstance(e, exc_type) for exc_type in stop_on):
                        if log_attempts:
                            logger.error(f"Non-retryable error in {func.__name__}: {e}")
                        raise

                    # Check if this error should trigger a retry
                    should_retry = any(isinstance(e, exc_type) for exc_type in retry_on)

                    if not should_retry or attempt == max_attempts - 1:
                        if log_attempts:
                            logger.error(f"Final attempt failed for {func.__name__}: {e}")
                        raise

                    # Calculate delay for next attempt
                    if exponential_backoff:
                        delay = min(base_delay * (2**attempt), max_delay)
                    else:
                        delay = base_delay

                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)

                    if log_attempts:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.2f}s"
                        )

                    await asyncio.sleep(delay)

            # This should never be reached, but just in case
            raise last_exception

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Check if this error should stop retries immediately
                    if any(isinstance(e, exc_type) for exc_type in stop_on):
                        if log_attempts:
                            logger.error(f"Non-retryable error in {func.__name__}: {e}")
                        raise

                    # Check if this error should trigger a retry
                    should_retry = any(isinstance(e, exc_type) for exc_type in retry_on)

                    if not should_retry or attempt == max_attempts - 1:
                        if log_attempts:
                            logger.error(f"Final attempt failed for {func.__name__}: {e}")
                        raise

                    # Calculate delay for next attempt
                    if exponential_backoff:
                        delay = min(base_delay * (2**attempt), max_delay)
                    else:
                        delay = base_delay

                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)

                    if log_attempts:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.2f}s"
                        )

                    import time

                    time.sleep(delay)

            # This should never be reached, but just in case
            raise last_exception

        # Return appropriate wrapper based on whether the function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Specific retry configurations for different services
def twitch_api_retry(func: Callable) -> Callable:
    """Retry configuration specifically for Twitch API calls."""
    return with_retry(
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0,
        exponential_backoff=True,
        jitter=True,
        retry_on=[
            ConnectionError,
            TimeoutError,
            OSError,  # Network-related errors
        ],
        stop_on=[
            NonRetryableError,
            # Add specific HTTP error codes that shouldn't be retried
        ],
        log_attempts=True,
    )(func)


def database_retry(func: Callable) -> Callable:
    """Retry configuration specifically for database operations."""
    return with_retry(
        max_attempts=5,
        base_delay=0.5,
        max_delay=10.0,
        exponential_backoff=True,
        jitter=True,
        retry_on=[
            ConnectionError,
            OSError,
            # Add specific database error types as needed
        ],
        stop_on=[
            NonRetryableError,
            # Add database-specific non-retryable errors
        ],
        log_attempts=True,
    )(func)


def recording_process_retry(func: Callable) -> Callable:
    """Retry configuration specifically for recording processes."""
    return with_retry(
        max_attempts=3,
        base_delay=2.0,
        max_delay=60.0,
        exponential_backoff=True,
        jitter=True,
        retry_on=[
            ConnectionError,
            TimeoutError,
            OSError,
            RetryableError,
        ],
        stop_on=[
            NonRetryableError,
            # Add process-specific non-retryable errors
        ],
        log_attempts=True,
    )(func)

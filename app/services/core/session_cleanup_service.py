"""
Session Cleanup Service - Fixes session authentication failures

Handles session expiration, cleanup, and proper validation
to resolve video sharing authentication issues.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session as DBSession
from app.models import Session
from app.database import SessionLocal
from app.config.constants import ASYNC_DELAYS

logger = logging.getLogger("streamvault")


class SessionCleanupService:
    """Service for managing session lifecycle and cleanup"""

    def __init__(self, session_timeout_hours: int = 24, cleanup_interval_minutes: int = 60):
        self.session_timeout_hours = session_timeout_hours
        self.cleanup_interval_minutes = cleanup_interval_minutes
        self.is_running = False
        self.cleanup_task = None

    async def start(self):
        """Start the session cleanup service"""
        if self.is_running:
            return

        self.is_running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_worker())
        logger.info(f"Session cleanup service started (timeout: {self.session_timeout_hours}h, interval: {self.cleanup_interval_minutes}m)")

    async def stop(self):
        """Stop the session cleanup service"""
        if not self.is_running:
            return

        self.is_running = False

        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Session cleanup service stopped")

    async def _cleanup_worker(self):
        """Worker that periodically cleans up expired sessions"""
        logger.info("Session cleanup worker started")

        while self.is_running:
            try:
                await self.cleanup_expired_sessions()

                # Wait for next cleanup cycle
                await asyncio.sleep(self.cleanup_interval_minutes * 60)

            except asyncio.CancelledError:
                logger.info("Session cleanup worker cancelled")
                break
            except Exception as e:
                logger.error(f"Session cleanup worker error: {e}")
                await asyncio.sleep(ASYNC_DELAYS.SESSION_CLEANUP_ERROR_WAIT)

        logger.info("Session cleanup worker stopped")

    async def cleanup_expired_sessions(self):
        """Clean up expired sessions from the database"""
        try:
            db = SessionLocal()

            # Calculate cutoff time
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.session_timeout_hours)

            # Find expired sessions
            expired_sessions = db.query(Session).filter(
                Session.created_at < cutoff_time
            ).all()

            if expired_sessions:
                expired_count = len(expired_sessions)

                # Delete expired sessions
                for session in expired_sessions:
                    db.delete(session)

                db.commit()
                logger.info(f"Cleaned up {expired_count} expired sessions")
            else:
                logger.debug("No expired sessions to clean up")

        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close()

    async def is_session_valid(self, token: str, db: DBSession) -> bool:
        """Check if session is valid and not expired"""
        try:
            session = db.query(Session).filter_by(token=token).first()
            if not session:
                return False

            # Check if session is expired
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.session_timeout_hours)
            if session.created_at < cutoff_time:
                # Session is expired, delete it immediately
                db.delete(session)
                db.commit()
                logger.debug(f"Removed expired session for token {token[:10]}...")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return False

    def get_stats(self) -> dict:
        """Get session cleanup statistics"""
        try:
            db = SessionLocal()

            total_sessions = db.query(Session).count()

            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.session_timeout_hours)
            expired_sessions = db.query(Session).filter(
                Session.created_at < cutoff_time
            ).count()

            return {
                'total_sessions': total_sessions,
                'expired_sessions': expired_sessions,
                'active_sessions': total_sessions - expired_sessions,
                'session_timeout_hours': self.session_timeout_hours,
                'cleanup_interval_minutes': self.cleanup_interval_minutes,
                'is_running': self.is_running
            }

        except Exception as e:
            logger.error(f"Error getting session stats: {e}")
            return {'error': str(e)}
        finally:
            if db:
                db.close()

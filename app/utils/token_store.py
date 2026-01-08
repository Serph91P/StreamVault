"""
Token Store Utility for Share Tokens

Manages temporary share tokens for video access with expiration.
Uses database storage for persistence and scalability.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Integer, DateTime
from app.database import SessionLocal, Base

logger = logging.getLogger("streamvault")


class ShareTokenModel(Base):
    """Database model for share tokens"""

    __tablename__ = "share_tokens"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String, unique=True, nullable=False)
    stream_id = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def store_share_token(token: str, stream_id: int, expiration_seconds: int) -> None:
    """Store a share token with expiration in database"""
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiration_seconds)

    with SessionLocal() as db:
        try:
            # Remove any existing token for this stream (optional cleanup)
            existing = db.query(ShareTokenModel).filter_by(stream_id=stream_id).first()
            if existing:
                db.delete(existing)

            # Create new token
            share_token = ShareTokenModel(token=token, stream_id=stream_id, expires_at=expires_at)
            db.add(share_token)
            db.commit()

            logger.info(f"Stored share token for stream {stream_id}, " f"expires at {expires_at}")

        except Exception as e:
            db.rollback()
            logger.error(f"Error storing share token: {e}")
            raise


def validate_share_token(token: str) -> Optional[int]:
    """Validate a share token and return the stream_id if valid"""
    with SessionLocal() as db:
        try:
            # Find the token
            share_token = db.query(ShareTokenModel).filter_by(token=token).first()

            if not share_token:
                return None

            # Check if token is expired
            now = datetime.now(timezone.utc)
            if now > share_token.expires_at:
                # Clean up expired token
                db.delete(share_token)
                db.commit()
                logger.debug(f"Removed expired share token: {token[:10]}...")
                return None

            return share_token.stream_id

        except Exception as e:
            logger.error(f"Error validating share token: {e}")
            return None


def cleanup_expired_tokens() -> int:
    """Clean up expired tokens and return count of removed tokens"""
    with SessionLocal() as db:
        try:
            now = datetime.now(timezone.utc)

            # Find expired tokens
            expired_tokens = db.query(ShareTokenModel).filter(ShareTokenModel.expires_at < now).all()

            expired_count = len(expired_tokens)

            if expired_count > 0:
                # Delete expired tokens
                db.query(ShareTokenModel).filter(ShareTokenModel.expires_at < now).delete()

                db.commit()
                logger.info(f"Cleaned up {expired_count} expired share tokens")

            return expired_count

        except Exception as e:
            db.rollback()
            logger.error(f"Error cleaning up expired tokens: {e}")
            return 0


def get_token_count() -> int:
    """Get the current number of active tokens"""
    with SessionLocal() as db:
        try:
            now = datetime.now(timezone.utc)
            count = db.query(ShareTokenModel).filter(ShareTokenModel.expires_at > now).count()
            return count
        except Exception as e:
            logger.error(f"Error getting token count: {e}")
            return 0


def get_tokens_for_stream(stream_id: int) -> list:
    """Get all active tokens for a specific stream"""
    with SessionLocal() as db:
        try:
            now = datetime.now(timezone.utc)
            tokens = (
                db.query(ShareTokenModel)
                .filter(ShareTokenModel.stream_id == stream_id, ShareTokenModel.expires_at > now)
                .all()
            )

            return [
                {
                    "token": token.token,
                    "expires_at": token.expires_at.isoformat(),
                    "created_at": token.created_at.isoformat(),
                }
                for token in tokens
            ]
        except Exception as e:
            logger.error(f"Error getting tokens for stream {stream_id}: {e}")
            return []


def get_all_tokens(db: Session) -> list:
    """Get all share tokens (for admin purposes)"""
    try:
        tokens = db.query(ShareTokenModel).order_by(ShareTokenModel.created_at.desc()).all()
        return tokens
    except Exception as e:
        logger.error(f"Error getting all tokens: {e}")
        return []

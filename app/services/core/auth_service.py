from sqlalchemy.orm import Session as DBSession
from app.models import User, Session
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import secrets
import logging
from typing import Optional
from app.schemas.auth import UserCreate, UserResponse
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("streamvault")

ph = PasswordHasher()

class AuthService:
    def __init__(self, db: DBSession):
        self.db = db
        self.session_timeout_hours = 24  # 24 hour session timeout for production

    async def admin_exists(self) -> bool:
        return bool(self.db.query(User).filter_by(is_admin=True).first())

    async def create_admin(self, user_data: UserCreate) -> UserResponse:
        hashed_password = ph.hash(user_data.password)
        admin = User(
            username=user_data.username,
            password=hashed_password,
            is_admin=True
        )
        self.db.add(admin)
        self.db.commit()
        return UserResponse.model_validate(admin)

    async def validate_login(self, username: str, password: str) -> Optional[User]:
        user = self.db.query(User).filter_by(username=username).first()
        if user:
            try:
                ph.verify(user.password, password)
                return user
            except VerifyMismatchError:
                return None
        return None

    async def create_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        session = Session(user_id=user_id, token=token)
        self.db.add(session)
        self.db.commit()
        return token

    async def validate_session(self, token: str) -> bool:
        """Validate session with automatic cleanup of expired sessions"""
        try:
            session = self.db.query(Session).filter_by(token=token).first()
            if not session:
                return False
                
            # Check if session is expired (production fix for multi-user auth issues)
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.session_timeout_hours)
            if session.created_at < cutoff_time:
                # Session is expired, delete it immediately
                self.db.delete(session)
                self.db.commit()
                logger.debug(f"Removed expired session for token {token[:10]}...")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return False

    async def refresh_session(self, token: str) -> bool:
        """Refresh a valid session by updating its created_at to now (sliding expiration)."""
        try:
            session = self.db.query(Session).filter_by(token=token).first()
            if not session:
                return False

            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.session_timeout_hours)
            if session.created_at < cutoff_time:
                # Expired - remove and reject
                self.db.delete(session)
                self.db.commit()
                logger.debug("Tried to refresh expired session; deleted")
                return False

            # Refresh timestamp to extend session
            session.created_at = datetime.now(timezone.utc)
            self.db.add(session)
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Error refreshing session: {e}")
            self.db.rollback()
            return False
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions (can be called periodically)"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.session_timeout_hours)
            
            expired_sessions = self.db.query(Session).filter(
                Session.created_at < cutoff_time
            ).all()
            
            expired_count = len(expired_sessions)
            
            if expired_count > 0:
                for session in expired_sessions:
                    self.db.delete(session)
                
                self.db.commit()
                logger.info(f"Cleaned up {expired_count} expired sessions")
                
            return expired_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            self.db.rollback()
            return 0

    async def delete_session(self, token: str) -> bool:
        """Delete a specific session token"""
        try:
            session = self.db.query(Session).filter_by(token=token).first()
            if session:
                self.db.delete(session)
                self.db.commit()
                logger.debug(f"Deleted session for token {token[:10]}...")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            self.db.rollback()
            return False

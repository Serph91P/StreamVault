"""Blocking auth maintenance; callers offload this complete resource scope."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.services.core.auth_service import AuthService


def cleanup_expired_sessions(
    session_factory: Callable[[], Session], settings: Settings | None
) -> int:
    with session_factory() as db:
        return AuthService(db=db, settings=settings).cleanup_expired_sessions_sync()

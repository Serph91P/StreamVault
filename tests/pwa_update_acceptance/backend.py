"""Isolated real factory, auth, router and canonical PWA bytes; no response overlays.

The runner supplies a fresh SQLite path and a synthetic local account. Production
lifespan is disabled at uvicorn so no external provider/background jobs start.
"""

import os
from pydantic import SecretStr

from app.config.settings import settings
from app.database import Base, SessionLocal, database_lifecycle
from app.models import GlobalSettings, SystemState, User
from app.services.core.auth_service import AuthService
from app.main import create_app

settings.USE_SECURE_COOKIES = False
settings.auth_jwt_secret = SecretStr(os.environ["PWA_TEST_JWT"])
with database_lifecycle.sync_engine.begin() as connection:
    connection.exec_driver_sql("BEGIN")
    Base.metadata.create_all(connection)
with SessionLocal() as db:
    db.add(
        User(
            username="synthetic-pwa-admin",
            is_admin=True,
            is_active=True,
            password=AuthService(db).hash_password(os.environ["PWA_TEST_PASSWORD"]),
        )
    )
    db.add(SystemState(id=1, welcome_completed=True))
    db.add(GlobalSettings(supported_codecs="h264,h265"))
    db.commit()
app = create_app(settings=settings)
assert not app.dependency_overrides

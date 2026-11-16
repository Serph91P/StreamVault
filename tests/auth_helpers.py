"""Real synthetic credentials for lightweight business-route fixtures.

These fixtures do not prove middleware boundaries; test_recording_capabilities
owns that full create_app matrix. Do not override identity or authorization.
"""

from pydantic import SecretStr

from app.config.settings import Settings
from app.dependencies import get_application_session_factory
from app.models import User
from app.services.core.auth_service import AuthService


def admin_headers(app, sessions):
    secret = SecretStr(
        "synthetic-business-route-jwt-key-at-least-thirty-two-characters"
    )
    settings = getattr(app.state, "settings", None)
    if settings is None:
        settings = Settings(ENVIRONMENT="test", auth_jwt_secret=secret, _env_file=None)
    settings = settings.model_copy(update={"auth_jwt_secret": secret})
    app.state.settings = settings
    app.dependency_overrides[get_application_session_factory] = lambda: sessions
    with sessions() as db:
        user = User(
            username="synthetic-contract-admin",
            password="unused",
            is_active=True,
            is_admin=True,
        )
        db.add(user)
        db.commit()
        token = AuthService(db, settings).create_access_token(user)
    return {"Authorization": f"Bearer {token}"}

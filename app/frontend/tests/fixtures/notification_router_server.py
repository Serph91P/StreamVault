"""Isolated, credential-free notification Router/SQLite harness, not the app factory.

Run from repository root with PYTHONPATH=. and a fresh explicit --database path:
  uv run python app/frontend/tests/fixtures/notification_router_server.py --database "$TMPDIR/notifications.sqlite"
Then run the issue904 Playwright config with STREAMVAULT_NOTIFICATION_ROUTER_URL
set to http://127.0.0.1:4189 to forward notification HTTP to this real router.
No production lifespan, authentication, provider or environment-file loading is
involved. The surrounding browser HTTP/WebSocket fixtures remain synthetic.
"""

import argparse
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uvicorn

from app.database import get_db
from app.models import NotificationState
from app.routes.notifications import router


def create_router_app(database: Path) -> FastAPI:
    engine = create_engine(
        f"sqlite:///{database.resolve()}", connect_args={"check_same_thread": False}
    )
    NotificationState.__table__.create(engine, checkfirst=True)
    sessions = sessionmaker(bind=engine)

    def isolated_db():
        with sessions() as session:
            yield session

    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_db] = isolated_db
    return application


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--port", type=int, default=4189)
    args = parser.parse_args()
    uvicorn.run(create_router_app(args.database), host="0.0.0.0", port=args.port)

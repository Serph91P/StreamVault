"""Stable Uvicorn entry point; composition lives in the application factory."""

from app.bootstrap.application import app, create_app
from app.lifespan import lifespan

__all__ = ["app", "create_app", "lifespan"]

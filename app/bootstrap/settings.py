"""Runtime-only configuration resolution for the composition/API boundary."""

from fastapi import FastAPI

from app.config.settings import Settings, get_settings


def resolve_app_settings(application: FastAPI) -> Settings:
    # FastAPI state is dynamic; legacy bare adapters keep default-config behavior.
    configuration: Settings | None = getattr(application.state, "settings", None)
    if configuration is None:
        # A cached default may already contain another database's hydrated keys.
        configuration = (
            get_settings()
            if getattr(application.state, "legacy_default", True)
            else Settings()
        )
        application.state.settings = configuration
    return configuration

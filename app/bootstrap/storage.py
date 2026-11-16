"""Runtime-only creation of the existing storage layout."""

from pathlib import Path

from app.config.settings import Settings


def prepare_storage_directories(settings: Settings) -> None:
    data = Path("/app/data") if Path("/app/data").exists() else Path("app/data")
    data.mkdir(parents=True, exist_ok=True)
    recordings = Path(settings.RECORDING_DIRECTORY)
    recordings.mkdir(parents=True, exist_ok=True)
    for name in ("profiles", "categories", "artwork", "thumbnails"):
        (recordings / ".media" / name).mkdir(parents=True, exist_ok=True)

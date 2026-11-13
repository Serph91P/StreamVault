"""Recording config fallback/cache policy uses actual scoped catalog rows."""

from datetime import datetime
import sqlite3

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.config.settings import Settings
from app.database import Base
from app.models import RecordingSettings, Streamer, StreamerRecordingSettings
from app.services.recording.config_manager import ConfigManager, FILENAME_PRESETS


@pytest.fixture
def configuration_catalog(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'configuration.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as db:
        db.add(Streamer(id=1, username="scoped", twitch_id="scoped"))
        db.commit()
    manager = ConfigManager(
        session_factory=factory,
        settings=Settings(
            ENVIRONMENT="test",
            RECORDING_DIRECTORY=str(tmp_path / "owned"),
            _env_file=None,
        ),
    )
    try:
        yield manager, factory, engine
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "scenario",
    [
        "missing-global",
        "missing-channel",
        "global-disabled",
        "channel-disabled",
        "inherited",
        "overridden",
        "nullable-defaults",
    ],
)
def test_recording_configuration_fallbacks_and_cache_reloads(
    configuration_catalog, scenario
):
    manager, factory, engine = configuration_catalog
    with factory() as db:
        if scenario != "missing-global":
            db.add(
                RecordingSettings(
                    id=1,
                    enabled=scenario != "global-disabled",
                    default_quality="480p",
                    filename_template="{streamer}",
                    max_streams_per_streamer=2,
                )
            )
        if scenario != "missing-channel":
            db.add(
                StreamerRecordingSettings(
                    streamer_id=1,
                    enabled=scenario != "channel-disabled",
                    quality="720p" if scenario == "overridden" else None,
                    custom_filename="{title}" if scenario == "overridden" else None,
                    max_streams=3 if scenario == "overridden" else 0,
                )
            )
        db.commit()
        if scenario != "overridden":
            # INSERT(None) applies the legacy best default; persist an actual
            # NULL via UPDATE to exercise the already-accepted inheritance port.
            db.execute(update(StreamerRecordingSettings).values(quality=None))
            db.commit()
        if scenario == "nullable-defaults":
            db.execute(
                update(RecordingSettings).values(
                    default_quality=None,
                    filename_template=None,
                    max_streams_per_streamer=None,
                )
            )
            db.commit()
    assert manager.is_recording_enabled(1) is (
        scenario in {"inherited", "overridden", "nullable-defaults"}
    )
    assert manager.get_quality_setting(1) == (
        "720p"
        if scenario == "overridden"
        else "best"
        if scenario in {"missing-global", "nullable-defaults"}
        else "480p"
    )
    assert manager.get_filename_template(1) == (
        "{title}"
        if scenario == "overridden"
        else FILENAME_PRESETS["default"]
        if scenario in {"missing-global", "nullable-defaults"}
        else "{streamer}"
    )
    assert manager.get_max_streams(1) == (
        3
        if scenario == "overridden"
        else 0
        if scenario in {"missing-global", "nullable-defaults"}
        else 2
    )
    assert manager.get_check_interval() == 30
    assert manager.get_config_value("absent", "fallback") == "fallback"
    assert manager.get_config_value("enabled", "fallback") == (
        "fallback" if scenario == "missing-global" else scenario != "global-disabled"
    )
    assert manager.get_recordings_directory().endswith("/owned")
    if scenario not in {"missing-global", "missing-channel"}:
        with factory() as db:
            db.execute(update(RecordingSettings).values(enabled=False))
            db.commit()
        manager.invalidate_cache()
        assert manager.last_refresh == datetime.min and not manager._streamer_settings
        assert not manager.is_recording_enabled(1)
    assert engine.pool.checkedout() == 0


@pytest.mark.parametrize("failure", ["schema", "connection"])
def test_recording_config_catalog_failure_returns_no_borrowed_model(tmp_path, failure):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'missing.db'}"
        if failure == "schema"
        else f"sqlite:///{tmp_path / 'absent' / 'db.sqlite'}"
    )
    try:
        manager = ConfigManager(session_factory=sessionmaker(engine))
        assert manager.get_global_settings() is None
        assert manager.get_streamer_settings(1) is None
        assert manager.get_output_directory() == "/recordings"
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "error,expected",
    [
        (
            RuntimeError("relation recording_settings does not exist"),
            "table_not_exists",
        ),
        (ConnectionError("synthetic connection unavailable"), "connection_error"),
        (
            OperationalError("SELECT", None, sqlite3.OperationalError("missing table")),
            "schema_error",
        ),
        (ValueError("synthetic malformed value"), "unexpected_error"),
    ],
)
def test_database_failure_classification_is_specific(error, expected):
    assert (
        ConfigManager()._categorize_database_error(error, "RecordingSettings")
        == expected
    )

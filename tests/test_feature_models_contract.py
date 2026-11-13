"""Feature model extraction must preserve the exact pre-extraction database ABI."""

from __future__ import annotations

import ast
import importlib
import inspect as python_inspect
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, event
from sqlalchemy.orm import Session
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateIndex, CreateTable, CreateSchema, DropSchema

import app.models as models


FEATURES = {
    "identity": ("User", "Session", "RefreshToken", "ApiKey"),
    "streams": ("Streamer", "Stream", "StreamEvent", "StreamMetadata"),
    "recordings": (
        "Recording",
        "RecordingSettings",
        "StreamerRecordingSettings",
        "ActiveRecordingState",
        "RecordingProcessingState",
    ),
    "notifications": ("NotificationSettings", "NotificationState", "PushSubscription"),
    "system": ("GlobalSettings", "SystemState", "SystemConfig"),
    "upstream": ("TwitchUpstreamLease", "TwitchUpstreamCoordinationState"),
    "proxies": ("ProxySettings",),
    "video_catalog": ("VideoCatalogEntry",),
    "background_task": ("BackgroundTask", "BackgroundTaskDependency"),
}


def snapshot_model_schema() -> dict:
    """Compile SQLite/PostgreSQL ABI without opening a database or reading rows."""
    result = {}
    for name in models.__all__:
        model = getattr(models, name)
        mapper = inspect(model)
        table = model.__table__
        result[name] = {
            "table": table.name,
            "columns": [
                {
                    "name": column.name,
                    "attribute": mapper.get_property_by_column(column).key,
                    "nullable": column.nullable,
                    "autoincrement": column.autoincrement,
                    "default": str(column.default.arg)
                    if column.default is not None
                    else None,
                    "onupdate": str(column.onupdate.arg)
                    if column.onupdate is not None
                    else None,
                }
                for column in table.columns
            ],
            "relationships": {
                relation.key: {
                    "target": relation.mapper.class_.__name__,
                    "uselist": relation.uselist,
                    "cascade": sorted(relation.cascade),
                    "lazy": relation.lazy,
                    "back_populates": relation.back_populates,
                }
                for relation in mapper.relationships
            },
            "ddl": {
                dialect.name: {
                    "table": str(CreateTable(table).compile(dialect=dialect)),
                    "indexes": sorted(
                        str(CreateIndex(index).compile(dialect=dialect))
                        for index in table.indexes
                    ),
                }
                for dialect in (sqlite.dialect(), postgresql.dialect())
            },
        }
    return result


@pytest.mark.parametrize("feature,names", FEATURES.items())
def test_feature_mappings_share_a_native_typed_declarative_base(feature, names):
    from sqlalchemy.orm import DeclarativeBase
    from app.database import Base

    assert issubclass(Base, DeclarativeBase)
    for name in names:
        model = getattr(models, name)
        assert issubclass(model, Base)
        assert model.registry is Base.registry
        assert model.metadata is Base.metadata


@pytest.mark.parametrize("feature,names", FEATURES.items())
def test_models_have_feature_local_typed_definitions_and_stable_aliases(
    feature, names
) -> None:
    legacy = importlib.import_module("app.models._legacy")
    for name in names:
        model = getattr(models, name)
        assert model.__module__ == f"app.models.{feature}"
        feature_module = importlib.import_module(f"app.models.{feature}")
        assert getattr(feature_module, name) is model
        if feature in {"video_catalog", "background_task"}:
            assert not hasattr(legacy, name)  # Added by #1045, never legacy exports.
        else:
            assert getattr(legacy, name) is model
        node = ast.parse(python_inspect.getsource(model)).body[0]
        annotated = {
            field.target.id: field.annotation
            for field in node.body
            if isinstance(field, ast.AnnAssign) and isinstance(field.target, ast.Name)
        }
        mapper = inspect(model)
        for attribute in (*mapper.column_attrs, *mapper.relationships):
            assert attribute.key in annotated, (name, attribute.key)
            annotation = annotated[attribute.key]
            assert isinstance(annotation, ast.Subscript)
            assert (
                isinstance(annotation.value, ast.Name)
                and annotation.value.id == "Mapped"
            )


def test_feature_model_metadata_preserves_pre_extraction_sqlite_and_postgres_abi() -> (
    None
):
    baseline = json.loads(
        (Path(__file__).parent / "fixtures" / "model-schema-baseline.json").read_text()
    )
    additions = json.loads(
        (Path(__file__).parent / "fixtures" / "accepted-develop-1045.json").read_text()
    )["models"]
    current = snapshot_model_schema()
    for name, definition in additions.items():
        assert current.pop(name) == definition
    assert current == baseline


def test_feature_relationship_graph_round_trips_in_an_isolated_database(
    tmp_path,
) -> None:
    url = os.environ.get(
        "STREAMVAULT_POSTGRES_TEST_URL", f"sqlite:///{tmp_path / 'models.db'}"
    )
    engine = create_engine(url)
    schema = None
    if engine.dialect.name == "postgresql":
        schema = "feature_models_" + uuid.uuid4().hex
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        engine = engine.execution_options(schema_translate_map={None: schema})
    tables = [getattr(models, name).__table__ for name in models.__all__]
    now = datetime.now(timezone.utc)
    try:
        with engine.begin() as connection:
            models.User.metadata.create_all(connection, tables=tables)
        with Session(engine) as session:
            user = models.User(username="feature-graph-user", password="test-only")
            streamer = models.Streamer(
                twitch_id="feature-graph-streamer", username="feature-graph"
            )
            stream = models.Stream(
                streamer=streamer, title="Feature graph", started_at=now
            )
            recording = models.Recording(
                stream=stream, status="recording", start_time=now
            )
            favorite = models.FavoriteCategory(
                user=user,
                category=models.Category(
                    twitch_id="feature-graph-category", name="Graph"
                ),
            )
            preferences = models.StreamerRecordingSettings(
                streamer=streamer, quality="best"
            )
            notifications = models.NotificationSettings(streamer=streamer)
            read_state = models.NotificationState(user=user, last_read_timestamp=now)
            metadata = models.StreamMetadata(
                stream=stream, nfo_path="/synthetic/graph.nfo"
            )
            active = models.ActiveRecordingState(
                stream=stream,
                recording=recording,
                process_id=123,
                process_identifier="synthetic-no-child",
                streamer_name=streamer.username,
                started_at=now,
                last_heartbeat=now,
                ts_output_path="/synthetic/graph.ts",
            )
            active.set_config({"quality": "best"})
            session.add_all(
                [favorite, preferences, notifications, read_state, metadata, active]
            )
            for number, status in enumerate(("processing", "completed", None), 1):
                other = models.Streamer(
                    twitch_id=f"graph-other-{number}", username=f"graph-other-{number}"
                )
                session.add(other)
                if status is not None:
                    session.add(
                        models.Recording(
                            stream=models.Stream(streamer=other),
                            start_time=now,
                            status=status,
                        )
                    )
            session.commit()
            ids = user.id, streamer.id, stream.id, recording.id
        with Session(engine) as session:
            user, streamer, stream, recording = [
                session.get(model, key)
                for model, key in zip(
                    (models.User, models.Streamer, models.Stream, models.Recording),
                    ids,
                    strict=True,
                )
            ]
            assert user.favorite_categories[0].category.name == "Graph"
            assert user.notification_state[0].user is user
            assert streamer.recording_settings.quality == "best"
            assert streamer.notification_settings[0].streamer is streamer
            assert streamer.streams == [stream]
            assert stream.streamer is streamer
            assert stream.stream_metadata.nfo_path == "/synthetic/graph.nfo"
            assert stream.recordings == [recording]
            assert stream.active_recording_state.recording is recording
            assert stream.active_recording_state.get_config() == {"quality": "best"}
            assert recording.stream is stream
            # Getter access must not run one hidden query per ORM instance.
            statements = []

            def observed(*_args):
                statements.append(True)

            event.listen(engine, "before_cursor_execute", observed)
            try:
                rows = session.query(models.Streamer).order_by(models.Streamer.id).all()
                assert [row.is_recording for row in rows] == [True, False, False, False]
                assert len(statements) == 1
                session.expunge_all()
                assert [row.is_recording for row in rows] == [True, False, False, False]
                assert len(statements) == 1
            finally:
                event.remove(engine, "before_cursor_execute", observed)
        with Session(engine) as session:
            recording = session.get(models.Recording, ids[3])
            recording.status = "completed"
            session.commit()
        with Session(engine) as session:
            assert session.get(models.Streamer, ids[1]).is_recording is False
        assert models.Streamer().is_recording is False
    finally:
        with engine.begin() as connection:
            if schema is not None:
                connection.execute(DropSchema(schema, cascade=True))
            else:
                models.User.metadata.drop_all(connection, tables=tables)
        engine.dispose()

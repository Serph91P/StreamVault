"""
Migration: 039_add_unique_twitch_stream_id

Deduplicates streams sharing the same twitch_stream_id and enforces
uniqueness with a UNIQUE index on streams.twitch_stream_id.

Background:
- stream.online dedup in app/events/handler_registry.py relies on
  twitch_stream_id being unique per Stream row, but the schema only had a
  non-unique index. Duplicate webhook deliveries could create multiple
  Stream rows for the same Twitch stream.

Cleanup semantics (per set of rows sharing a non-NULL twitch_stream_id):
- Survivor selection: prefer the row with Recordings attached, then the row
  with StreamEvents attached, then the lowest id.
- NULL columns on the survivor (title, category, timestamps, recording_path,
  episode_number) are filled from the duplicates in id order.
- stream_events, recordings and recording_processing_state rows are
  repointed to the survivor.
- One-row-per-stream tables (stream_metadata, active_recordings_state) keep
  the survivor's row if it exists; otherwise one duplicate row is repointed.
  Leftover rows are deleted together with the duplicate streams.

Index:
- Drops the old non-unique indexes (idx_streams_twitch_stream_id from
  migration 004, ix_streams_twitch_stream_id from SQLAlchemy create_all)
  and creates a UNIQUE index named ix_streams_twitch_stream_id to match the
  model definition. twitch_stream_id stays nullable; both PostgreSQL and
  SQLite allow multiple NULLs in a unique index.
"""

import logging

from sqlalchemy import bindparam, inspect, text
from app.database import engine

logger = logging.getLogger("streamvault")

SCRIPT_NAME = __name__.split(".")[-1] + ".py"

# Nullable scalar columns merged from duplicates into the survivor
MERGE_COLUMNS = (
    "title",
    "category_name",
    "language",
    "started_at",
    "ended_at",
    "recording_path",
    "episode_number",
)

# Tables with a many-to-one FK to streams.id: all rows are repointed
MANY_PER_STREAM_TABLES = (
    "stream_events",
    "recordings",
    "recording_processing_state",
)

# Tables with at most one row per stream: repoint only if the survivor has none
ONE_PER_STREAM_TABLES = (
    "stream_metadata",
    "active_recordings_state",
)

SQL_DROP_OLD_INDEXES = (
    "DROP INDEX IF EXISTS idx_streams_twitch_stream_id",
    "DROP INDEX IF EXISTS ix_streams_twitch_stream_id",
)

SQL_CREATE_UNIQUE_INDEX = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_streams_twitch_stream_id "
    "ON streams (twitch_stream_id)"
)


def _existing_tables(conn, table_names):
    """Return only the table names that actually exist in this database."""
    present = set(inspect(conn).get_table_names())
    return [name for name in table_names if name in present]


def _pick_survivor(conn, twitch_stream_id):
    """Return (survivor_id, duplicate_ids) for one set of duplicate streams."""
    rows = conn.execute(
        text(
            """
            SELECT s.id,
                   (SELECT COUNT(*) FROM recordings r WHERE r.stream_id = s.id) AS rec_count,
                   (SELECT COUNT(*) FROM stream_events e WHERE e.stream_id = s.id) AS ev_count
            FROM streams s
            WHERE s.twitch_stream_id = :tsid
            ORDER BY s.id
            """
        ),
        {"tsid": twitch_stream_id},
    ).fetchall()

    ranked = sorted(rows, key=lambda r: (r.rec_count == 0, r.ev_count == 0, r.id))
    survivor_id = ranked[0].id
    duplicate_ids = [r.id for r in rows if r.id != survivor_id]
    return survivor_id, duplicate_ids


def _merge_scalar_columns(conn, survivor_id, duplicate_ids):
    """Fill NULL columns on the survivor from the duplicates (in id order)."""
    columns = ", ".join(MERGE_COLUMNS)
    survivor = conn.execute(
        text(f"SELECT {columns} FROM streams WHERE id = :sid"),
        {"sid": survivor_id},
    ).mappings().one()

    missing = [col for col in MERGE_COLUMNS if survivor[col] is None]
    if not missing:
        return

    updates = {}
    for dup_id in duplicate_ids:
        dup = conn.execute(
            text(f"SELECT {columns} FROM streams WHERE id = :sid"),
            {"sid": dup_id},
        ).mappings().one()
        for col in missing:
            if col not in updates and dup[col] is not None:
                updates[col] = dup[col]

    if updates:
        assignments = ", ".join(f"{col} = :{col}" for col in updates)
        conn.execute(
            text(f"UPDATE streams SET {assignments} WHERE id = :sid"),
            {**updates, "sid": survivor_id},
        )


def _repoint_children(conn, survivor_id, duplicate_ids):
    """Repoint child-table FKs from the duplicates to the survivor."""
    params = {"sid": survivor_id, "dup_ids": duplicate_ids}

    for table in _existing_tables(conn, MANY_PER_STREAM_TABLES):
        conn.execute(
            text(
                f"UPDATE {table} SET stream_id = :sid WHERE stream_id IN :dup_ids"
            ).bindparams(bindparam("dup_ids", expanding=True)),
            params,
        )

    for table in _existing_tables(conn, ONE_PER_STREAM_TABLES):
        survivor_has_row = conn.execute(
            text(f"SELECT 1 FROM {table} WHERE stream_id = :sid LIMIT 1"),
            {"sid": survivor_id},
        ).first()
        if not survivor_has_row:
            candidate = conn.execute(
                text(
                    f"SELECT id FROM {table} WHERE stream_id IN :dup_ids "
                    "ORDER BY id LIMIT 1"
                ).bindparams(bindparam("dup_ids", expanding=True)),
                {"dup_ids": duplicate_ids},
            ).first()
            if candidate:
                conn.execute(
                    text(f"UPDATE {table} SET stream_id = :sid WHERE id = :row_id"),
                    {"sid": survivor_id, "row_id": candidate.id},
                )
        # Delete leftovers explicitly: SQLite test databases don't enforce
        # FK cascades, so relying on ON DELETE CASCADE is not enough.
        conn.execute(
            text(f"DELETE FROM {table} WHERE stream_id IN :dup_ids").bindparams(
                bindparam("dup_ids", expanding=True)
            ),
            {"dup_ids": duplicate_ids},
        )


def _deduplicate_streams(conn):
    duplicate_ids_rows = conn.execute(
        text(
            """
            SELECT twitch_stream_id
            FROM streams
            WHERE twitch_stream_id IS NOT NULL
            GROUP BY twitch_stream_id
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    if not duplicate_ids_rows:
        logger.info("Migration 039: no duplicate twitch_stream_id rows found")
        return

    logger.info(
        f"Migration 039: found {len(duplicate_ids_rows)} twitch_stream_id values "
        "with duplicate stream rows, merging..."
    )

    for row in duplicate_ids_rows:
        tsid = row.twitch_stream_id
        survivor_id, duplicate_ids = _pick_survivor(conn, tsid)
        logger.info(
            f"Migration 039: twitch_stream_id={tsid} keeping stream {survivor_id}, "
            f"merging duplicates {duplicate_ids}"
        )
        _merge_scalar_columns(conn, survivor_id, duplicate_ids)
        _repoint_children(conn, survivor_id, duplicate_ids)
        conn.execute(
            text("DELETE FROM streams WHERE id IN :dup_ids").bindparams(
                bindparam("dup_ids", expanding=True)
            ),
            {"dup_ids": duplicate_ids},
        )


def upgrade(target_engine=None):
    eng = target_engine or engine
    with eng.begin() as conn:
        _deduplicate_streams(conn)
        for statement in SQL_DROP_OLD_INDEXES:
            conn.execute(text(statement))
        conn.execute(text(SQL_CREATE_UNIQUE_INDEX))
    logger.info("✅ Migration 039: unique index on streams.twitch_stream_id created")


def downgrade(target_engine=None):
    """Restore the non-unique index. The duplicate-row merge is irreversible."""
    eng = target_engine or engine
    with eng.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ix_streams_twitch_stream_id"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_streams_twitch_stream_id "
                "ON streams (twitch_stream_id)"
            )
        )

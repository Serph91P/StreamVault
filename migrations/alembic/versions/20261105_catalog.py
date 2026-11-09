"""Persist the bounded video catalog filesystem read model.

Revision ID: 20261105_catalog
Revises: 20260922_legacy
"""

from alembic import op
import sqlalchemy as sa

revision = "20261105_catalog"
down_revision = "20260922_legacy"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "video_catalog_entries",
        sa.Column(
            "stream_id",
            sa.Integer(),
            sa.ForeignKey("streams.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recording_id", sa.Integer(), nullable=True),
        sa.Column(
            "is_recording", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "has_thumbnail", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("state", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_type", sa.String(64), nullable=True),
        sa.Column("dirty", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_video_catalog_entries_state", "video_catalog_entries", ["state"]
    )
    op.create_index(
        "ix_video_catalog_entries_checked_at", "video_catalog_entries", ["checked_at"]
    )
    op.create_index(
        "ix_video_catalog_entries_dirty", "video_catalog_entries", ["dirty"]
    )


def downgrade():
    op.drop_table("video_catalog_entries")

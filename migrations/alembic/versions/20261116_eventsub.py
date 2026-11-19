"""Preserve EventSub chapter identity across partial commits and restarts.

Revision ID: 20261116_eventsub
Revises: 20261106_tasks
"""

from alembic import op
import sqlalchemy as sa

revision = "20261116_eventsub"
down_revision = "20261106_tasks"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "stream_events", sa.Column("delivery_key", sa.String(64), nullable=True)
    )
    op.create_index(
        "ix_stream_events_delivery_key", "stream_events", ["delivery_key"], unique=True
    )


def downgrade():
    op.drop_index("ix_stream_events_delivery_key", table_name="stream_events")
    op.drop_column("stream_events", "delivery_key")

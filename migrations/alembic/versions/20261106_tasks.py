"""Durable bounded background queue admission.

Revision ID: 20261106_tasks
Revises: 20261105_catalog
"""

from alembic import op
import sqlalchemy as sa

revision = "20261106_tasks"
down_revision = "20261105_catalog"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "background_tasks",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("task_type", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("streamer_key", sa.String(256), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("owner_token", sa.String(36)),
        sa.Column("owner_pid", sa.Integer()),
        sa.Column("owner_started", sa.Float()),
        sa.Column("owner_host", sa.String(256)),
    )
    op.create_index("ix_background_tasks_dispatch", "background_tasks", ["status", "ready_at", "priority", "created_at"])
    op.create_table(
        "background_task_dependencies",
        sa.Column("task_id", sa.String(128), sa.ForeignKey("background_tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("dependency_id", sa.String(128), sa.ForeignKey("background_tasks.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("ix_background_task_dependencies_dependency_id", "background_task_dependencies", ["dependency_id"])


def downgrade():
    op.drop_table("background_task_dependencies")
    op.drop_table("background_tasks")

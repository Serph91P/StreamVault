"""Record the lossless handoff from the complete numbered migration ledger.

Revision ID: 20260922_legacy
Revises: None
"""

from collections.abc import Sequence

revision: str = "20260922_legacy"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """The legacy ledger already owns every schema and data change."""


def downgrade() -> None:
    """Never destroy legacy schema or data when removing only the stamp."""

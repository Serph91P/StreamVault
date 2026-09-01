"""Migration 026: defer proxy credential encryption until the schema is current."""


def upgrade():
    """Leave proxy rows untouched for the final post-schema migration."""
    print("Migration 026: Proxy credential encryption deferred")


def downgrade():
    """Migration 026 no longer changes proxy credential storage."""
    print("Migration 026 downgrade: No changes required")

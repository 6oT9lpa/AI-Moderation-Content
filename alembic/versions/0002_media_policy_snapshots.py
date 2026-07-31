"""Add versioned guild media policy snapshots and immutable audit history.

Revision ID: 0002_media_policy_snapshots
Revises: 0001_media_moderation_api
Create Date: 2026-07-31
"""

from alembic import op

revision = "0002_media_policy_snapshots"
down_revision = "0001_media_moderation_api"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE media_policy_snapshots (
            id BIGSERIAL PRIMARY KEY,
            platform TEXT NOT NULL CHECK (platform = 'discord'),
            guild_id TEXT NOT NULL CHECK (guild_id ~ '^[0-9]{1,32}$'),
            policy_type TEXT NOT NULL CHECK (policy_type = 'MEDIA'),
            schema_version TEXT NOT NULL CHECK (schema_version = 'media-policy-v1'),
            defaults_version TEXT NOT NULL,
            revision BIGINT NOT NULL CHECK (revision >= 1),
            policy_json JSONB NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT NOT NULL,
            UNIQUE (platform, guild_id, policy_type)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE media_policy_audit (
            id BIGSERIAL PRIMARY KEY,
            platform TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            operation TEXT NOT NULL CHECK (operation IN ('SAVE', 'RESET')),
            revision BIGINT NOT NULL,
            policy_json JSONB,
            updated_by TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX idx_media_policy_audit_scope ON media_policy_audit (platform, guild_id, created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_media_policy_audit_scope")
    op.execute("DROP TABLE IF EXISTS media_policy_audit")
    op.execute("DROP TABLE IF EXISTS media_policy_snapshots")

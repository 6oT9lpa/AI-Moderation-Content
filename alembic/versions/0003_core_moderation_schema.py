"""Make Alembic the sole source for the core moderation schema.

Revision ID: 0003_core_moderation_schema
Revises: 0002_media_policy_snapshots
"""

from alembic import op

revision = "0003_core_moderation_schema"
down_revision = "0002_media_policy_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in _TABLES:
        op.execute(statement)
    for statement in _INDEXES:
        op.execute(statement)


def downgrade() -> None:
    for table_name in (
        "ai_rule_match_events",
        "action_execution_logs",
        "policy_records",
        "ai_policy_versions",
        "ai_rule_definitions",
        "ai_feedback_labels",
        "ai_moderation_decisions",
        "ai_message_features",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")


_TABLES = (
    """
    CREATE TABLE IF NOT EXISTS ai_message_features (
        id BIGSERIAL PRIMARY KEY,
        event_id BIGINT NOT NULL UNIQUE REFERENCES ai_message_events(id) ON DELETE CASCADE,
        char_count INTEGER NOT NULL DEFAULT 0 CHECK (char_count >= 0),
        token_count INTEGER NOT NULL DEFAULT 0 CHECK (token_count >= 0),
        word_count INTEGER NOT NULL DEFAULT 0 CHECK (word_count >= 0),
        line_count INTEGER NOT NULL DEFAULT 0 CHECK (line_count >= 0),
        url_count INTEGER NOT NULL DEFAULT 0 CHECK (url_count >= 0),
        invite_count INTEGER NOT NULL DEFAULT 0 CHECK (invite_count >= 0),
        mention_count INTEGER NOT NULL DEFAULT 0 CHECK (mention_count >= 0),
        role_mention_count INTEGER NOT NULL DEFAULT 0 CHECK (role_mention_count >= 0),
        channel_mention_count INTEGER NOT NULL DEFAULT 0 CHECK (channel_mention_count >= 0),
        emoji_count INTEGER NOT NULL DEFAULT 0 CHECK (emoji_count >= 0),
        emoji_ratio NUMERIC(5,4) NOT NULL DEFAULT 0 CHECK (emoji_ratio BETWEEN 0 AND 1),
        caps_ratio NUMERIC(5,4) NOT NULL DEFAULT 0 CHECK (caps_ratio BETWEEN 0 AND 1),
        repeated_char_score NUMERIC(5,4) NOT NULL DEFAULT 0 CHECK (repeated_char_score BETWEEN 0 AND 1),
        duplicate_text_score NUMERIC(5,4) NOT NULL DEFAULT 0 CHECK (duplicate_text_score BETWEEN 0 AND 1),
        has_url BOOLEAN NOT NULL DEFAULT FALSE,
        has_invite BOOLEAN NOT NULL DEFAULT FALSE,
        has_shortener BOOLEAN NOT NULL DEFAULT FALSE,
        has_mixed_scripts BOOLEAN NOT NULL DEFAULT FALSE,
        has_zero_width BOOLEAN NOT NULL DEFAULT FALSE,
        has_suspicious_unicode BOOLEAN NOT NULL DEFAULT FALSE,
        is_reply BOOLEAN NOT NULL DEFAULT FALSE,
        message_age_seconds BIGINT,
        account_age_days INTEGER,
        member_age_days INTEGER,
        recent_user_messages_10s INTEGER NOT NULL DEFAULT 0 CHECK (recent_user_messages_10s >= 0),
        recent_user_messages_60s INTEGER NOT NULL DEFAULT 0 CHECK (recent_user_messages_60s >= 0),
        recent_user_messages_10m INTEGER NOT NULL DEFAULT 0 CHECK (recent_user_messages_10m >= 0),
        repeated_messages_10m INTEGER NOT NULL DEFAULT 0 CHECK (repeated_messages_10m >= 0),
        user_warnings_count INTEGER NOT NULL DEFAULT 0 CHECK (user_warnings_count >= 0),
        user_timeouts_count INTEGER NOT NULL DEFAULT 0 CHECK (user_timeouts_count >= 0),
        channel_is_ai_whitelisted BOOLEAN NOT NULL DEFAULT FALSE,
        features_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_moderation_decisions (
        id BIGSERIAL PRIMARY KEY,
        event_id BIGINT NOT NULL REFERENCES ai_message_events(id) ON DELETE CASCADE,
        policy_version TEXT NOT NULL DEFAULT 'default',
        decision_action TEXT NOT NULL,
        severity SMALLINT NOT NULL CHECK (severity BETWEEN 0 AND 5),
        reason_code TEXT,
        reason_text TEXT,
        action_taken BOOLEAN NOT NULL DEFAULT FALSE,
        action_success BOOLEAN,
        platform_error TEXT,
        punishment_id TEXT,
        review_status TEXT NOT NULL DEFAULT 'not_required',
        reviewed_by TEXT,
        reviewed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_feedback_labels (
        id BIGSERIAL PRIMARY KEY,
        event_id BIGINT NOT NULL REFERENCES ai_message_events(id) ON DELETE CASCADE,
        decision_id BIGINT REFERENCES ai_moderation_decisions(id) ON DELETE SET NULL,
        labels_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        primary_label TEXT,
        scam_subtype TEXT,
        severity SMALLINT CHECK (severity IS NULL OR severity BETWEEN 0 AND 5),
        recommended_action TEXT,
        moderator_id TEXT,
        feedback_type TEXT NOT NULL,
        is_false_positive BOOLEAN NOT NULL DEFAULT FALSE,
        is_false_negative BOOLEAN NOT NULL DEFAULT FALSE,
        needs_context BOOLEAN NOT NULL DEFAULT FALSE,
        annotator_confidence NUMERIC(5,4) CHECK (annotator_confidence IS NULL OR annotator_confidence BETWEEN 0 AND 1),
        annotation_source TEXT,
        notes TEXT,
        idempotency_key TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "ALTER TABLE ai_feedback_labels ADD COLUMN IF NOT EXISTS idempotency_key TEXT",
    """
    CREATE TABLE IF NOT EXISTS ai_rule_definitions (
        id BIGSERIAL PRIMARY KEY,
        rule_id TEXT NOT NULL,
        rule_type TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
        title TEXT NOT NULL,
        description TEXT,
        severity SMALLINT CHECK (severity IS NULL OR severity BETWEEN 0 AND 5),
        default_confidence NUMERIC(5,4) CHECK (default_confidence IS NULL OR default_confidence BETWEEN 0 AND 1),
        config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (rule_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_policy_versions (
        id BIGSERIAL PRIMARY KEY,
        policy_id TEXT NOT NULL,
        version TEXT NOT NULL,
        scope_type TEXT NOT NULL DEFAULT 'global',
        scope_id TEXT,
        is_active BOOLEAN NOT NULL DEFAULT FALSE,
        config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        activated_at TIMESTAMPTZ,
        UNIQUE (policy_id, version, scope_type, scope_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS policy_records (
        id BIGSERIAL PRIMARY KEY,
        policy_id TEXT NOT NULL UNIQUE,
        policy_type TEXT NOT NULL,
        scope_type TEXT NOT NULL,
        scope_id TEXT,
        platform TEXT,
        version TEXT NOT NULL,
        payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        priority INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS action_execution_logs (
        id BIGSERIAL PRIMARY KEY,
        message_id TEXT NOT NULL,
        decision_action TEXT NOT NULL,
        action TEXT NOT NULL,
        status TEXT NOT NULL,
        dry_run BOOLEAN NOT NULL DEFAULT FALSE,
        reason TEXT,
        platform TEXT,
        guild_id TEXT,
        channel_id TEXT,
        user_id TEXT,
        error TEXT,
        platform_response_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_rule_match_events (
        id BIGSERIAL PRIMARY KEY,
        event_id BIGINT NOT NULL REFERENCES ai_message_events(id) ON DELETE CASCADE,
        rule_id TEXT NOT NULL,
        rule_version INTEGER,
        severity SMALLINT CHECK (severity IS NULL OR severity BETWEEN 0 AND 5),
        confidence NUMERIC(5,4) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
        evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
)

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_ai_message_events_guild_created_at ON ai_message_events (guild_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_ai_message_events_user_created_at ON ai_message_events (user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_ai_message_events_channel_created_at ON ai_message_events (channel_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_ai_message_events_source ON ai_message_events (source)",
    "CREATE INDEX IF NOT EXISTS idx_ai_message_events_text_hash ON ai_message_events (text_hash)",
    "CREATE INDEX IF NOT EXISTS idx_ai_message_events_retention_until ON ai_message_events (retention_until)",
    "CREATE INDEX IF NOT EXISTS idx_ai_moderation_decisions_event_id ON ai_moderation_decisions (event_id)",
    "CREATE INDEX IF NOT EXISTS idx_ai_moderation_decisions_action ON ai_moderation_decisions (decision_action)",
    "CREATE INDEX IF NOT EXISTS idx_ai_moderation_decisions_created_at ON ai_moderation_decisions (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_ai_feedback_labels_event_id ON ai_feedback_labels (event_id)",
    "CREATE INDEX IF NOT EXISTS idx_ai_feedback_labels_primary_label ON ai_feedback_labels (primary_label)",
    "CREATE INDEX IF NOT EXISTS idx_ai_feedback_labels_feedback_type ON ai_feedback_labels (feedback_type)",
    "CREATE INDEX IF NOT EXISTS idx_ai_feedback_labels_annotation_source ON ai_feedback_labels (annotation_source)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_feedback_labels_idempotency_key ON ai_feedback_labels (idempotency_key) WHERE idempotency_key IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_ai_rule_definitions_rule_id ON ai_rule_definitions (rule_id)",
    "CREATE INDEX IF NOT EXISTS idx_ai_policy_versions_active ON ai_policy_versions (policy_id, scope_type, scope_id, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_policy_records_resolution ON policy_records (policy_type, scope_type, scope_id, platform, enabled, priority DESC)",
    "CREATE INDEX IF NOT EXISTS idx_action_execution_logs_message_id ON action_execution_logs (message_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_action_execution_logs_status ON action_execution_logs (status)",
    "CREATE INDEX IF NOT EXISTS idx_ai_rule_match_events_event_id ON ai_rule_match_events (event_id)",
    "CREATE INDEX IF NOT EXISTS idx_ai_rule_match_events_rule_id ON ai_rule_match_events (rule_id)",
)

"""Add versioned storage for media moderation.

Revision ID: 0001_media_moderation_api
Revises:
Create Date: 2026-07-31
"""

from alembic import op
from sqlalchemy import inspect

revision = "0001_media_moderation_api"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_message_events (
            id BIGSERIAL PRIMARY KEY,
            platform TEXT NOT NULL DEFAULT 'discord',
            message_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            thread_id TEXT,
            user_id TEXT NOT NULL,
            event_type TEXT NOT NULL DEFAULT 'message_create',
            source TEXT NOT NULL DEFAULT 'real_safe',
            raw_text TEXT,
            normalized_text TEXT,
            text_hash TEXT,
            language TEXT,
            reply_to_message_id TEXT,
            has_attachments BOOLEAN NOT NULL DEFAULT FALSE,
            attachment_count INTEGER NOT NULL DEFAULT 0 CHECK (attachment_count >= 0),
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMPTZ,
            retention_until TIMESTAMPTZ,
            UNIQUE (guild_id, message_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_media_attachments (
            id BIGSERIAL PRIMARY KEY,
            event_id BIGINT NOT NULL REFERENCES ai_message_events(id) ON DELETE CASCADE,
            attachment_id TEXT NOT NULL,
            file_name TEXT,
            file_type TEXT,
            content_type TEXT,
            declared_mime TEXT NOT NULL DEFAULT 'application/octet-stream',
            detected_mime TEXT,
            file_size BIGINT CHECK (file_size IS NULL OR file_size >= 0),
            width INTEGER CHECK (width IS NULL OR width >= 0),
            height INTEGER CHECK (height IS NULL OR height >= 0),
            aspect_ratio NUMERIC(10, 4),
            sha256 TEXT,
            phash TEXT,
            dhash TEXT,
            ahash TEXT,
            is_screenshot_like BOOLEAN NOT NULL DEFAULT FALSE,
            ocr_text TEXT,
            ocr_language TEXT,
            ocr_confidence NUMERIC(5, 4) CHECK (
                ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)
            ),
            ocr_text_hash TEXT,
            ocr_flags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            ocr_has_money BOOLEAN NOT NULL DEFAULT FALSE,
            ocr_has_casino BOOLEAN NOT NULL DEFAULT FALSE,
            ocr_has_crypto BOOLEAN NOT NULL DEFAULT FALSE,
            ocr_has_bonus BOOLEAN NOT NULL DEFAULT FALSE,
            ocr_has_payment_words BOOLEAN NOT NULL DEFAULT FALSE,
            known_scam_hash_match BOOLEAN NOT NULL DEFAULT FALSE,
            storage_uri TEXT,
            retention_until TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (event_id, attachment_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_analysis_results (
            id BIGSERIAL PRIMARY KEY,
            event_id BIGINT NOT NULL REFERENCES ai_message_events(id) ON DELETE CASCADE,
            attachment_id TEXT NOT NULL DEFAULT '__message__',
            stage TEXT NOT NULL,
            model_name TEXT,
            model_version TEXT,
            input_version TEXT,
            policy_version TEXT NOT NULL DEFAULT 'legacy',
            output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            label TEXT,
            labels_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            confidence NUMERIC(5, 4) CHECK (
                confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
            ),
            probabilities_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            rule_matches_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            risk_score INTEGER CHECK (risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)),
            risk_breakdown_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            latency_ms INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("ALTER TABLE ai_media_attachments ADD COLUMN IF NOT EXISTS declared_mime TEXT")
    op.execute("ALTER TABLE ai_media_attachments ADD COLUMN IF NOT EXISTS detected_mime TEXT")
    op.execute(
        "ALTER TABLE ai_media_attachments ADD COLUMN IF NOT EXISTS "
        "ocr_flags_json JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute("ALTER TABLE ai_media_attachments ADD COLUMN IF NOT EXISTS retention_until TIMESTAMPTZ")
    op.execute(
        "ALTER TABLE ai_media_attachments ADD COLUMN IF NOT EXISTS "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP"
    )
    op.execute(
        "UPDATE ai_media_attachments SET declared_mime = "
        "COALESCE(declared_mime, content_type, 'application/octet-stream')"
    )
    op.execute("ALTER TABLE ai_media_attachments ALTER COLUMN declared_mime SET NOT NULL")

    op.execute(
        "ALTER TABLE ai_analysis_results ADD COLUMN IF NOT EXISTS "
        "attachment_id TEXT NOT NULL DEFAULT '__message__'"
    )
    op.execute(
        "ALTER TABLE ai_analysis_results ADD COLUMN IF NOT EXISTS "
        "policy_version TEXT NOT NULL DEFAULT 'legacy'"
    )
    op.execute("UPDATE ai_analysis_results SET model_name = COALESCE(model_name, 'unknown')")
    op.execute("UPDATE ai_analysis_results SET model_version = COALESCE(model_version, 'unknown')")
    op.execute("UPDATE ai_analysis_results SET input_version = COALESCE(input_version, 'legacy')")
    # Execute as driver SQL because SQLAlchemy's text parser interprets the
    # colon inside the migration marker as a named bind parameter.
    op.get_bind().exec_driver_sql(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY event_id, attachment_id, stage, model_name,
                        model_version, input_version, policy_version
                    ORDER BY id
                ) AS duplicate_ordinal
            FROM ai_analysis_results
        )
        UPDATE ai_analysis_results AS result
        SET input_version = result.input_version || ':legacy-row-' || result.id::text
        FROM ranked
        WHERE result.id = ranked.id AND ranked.duplicate_ordinal > 1
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_ai_analysis_results_media_version'
                  AND conrelid = 'ai_analysis_results'::regclass
            ) THEN
                ALTER TABLE ai_analysis_results
                ADD CONSTRAINT uq_ai_analysis_results_media_version
                UNIQUE (
                    event_id, attachment_id, stage, model_name, model_version,
                    input_version, policy_version
                );
            END IF;
        END $$
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_media_attachments_retention "
        "ON ai_media_attachments (retention_until)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_media_attachments_event_attachment "
        "ON ai_media_attachments (event_id, attachment_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_analysis_results_attachment_stage "
        "ON ai_analysis_results (attachment_id, stage)"
    )
    if _table_exists("policy_records"):
        _remove_obsolete_label("policy_records", "payload_json")
    if _table_exists("ai_policy_versions"):
        _remove_obsolete_label("ai_policy_versions", "config_json")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ai_analysis_results_attachment_stage")
    op.execute("DROP INDEX IF EXISTS idx_ai_media_attachments_event_attachment")
    op.execute("DROP INDEX IF EXISTS idx_ai_media_attachments_retention")
    op.execute(
        "ALTER TABLE ai_analysis_results "
        "DROP CONSTRAINT IF EXISTS uq_ai_analysis_results_media_version"
    )
    op.execute("ALTER TABLE ai_analysis_results DROP COLUMN IF EXISTS policy_version")
    op.execute("ALTER TABLE ai_analysis_results DROP COLUMN IF EXISTS attachment_id")
    op.execute("ALTER TABLE ai_media_attachments DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE ai_media_attachments DROP COLUMN IF EXISTS retention_until")
    op.execute("ALTER TABLE ai_media_attachments DROP COLUMN IF EXISTS ocr_flags_json")
    op.execute("ALTER TABLE ai_media_attachments DROP COLUMN IF EXISTS detected_mime")
    op.execute("ALTER TABLE ai_media_attachments DROP COLUMN IF EXISTS declared_mime")


def _remove_obsolete_label(table_name: str, column_name: str) -> None:
    obsolete_label = "IMAGE_" + "SCAM"
    op.execute(
        f"""
        UPDATE {table_name}
        SET {column_name} = {column_name}
            #- ARRAY['label_weights', '{obsolete_label}']
            #- ARRAY['labels', '{obsolete_label}']
            #- ARRAY['confidence_thresholds', 'per_label_min_confidence', '{obsolete_label}']
        WHERE {column_name}::text LIKE '%{obsolete_label}%'
        """
    )
    op.execute(
        f"""
        UPDATE {table_name}
        SET {column_name} = jsonb_set(
            {column_name},
            '{{primary_label_priority}}',
            COALESCE(
                (
                    SELECT jsonb_agg(entry)
                    FROM jsonb_array_elements({column_name}->'primary_label_priority') AS entry
                    WHERE entry <> to_jsonb('{obsolete_label}'::text)
                ),
                '[]'::jsonb
            ),
            true
        )
        WHERE jsonb_typeof({column_name}->'primary_label_priority') = 'array'
          AND {column_name}->'primary_label_priority' @> jsonb_build_array('{obsolete_label}')
        """
    )


def _table_exists(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)

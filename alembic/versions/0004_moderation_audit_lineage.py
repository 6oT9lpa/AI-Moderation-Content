"""persist moderation request correlation lineage

Revision ID: 0004_moderation_audit_lineage
Revises: 0003_core_moderation_schema
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_moderation_audit_lineage"
down_revision = "0003_core_moderation_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_message_events", sa.Column("correlation_id", sa.String(64), nullable=True))
    op.add_column("ai_feedback_labels", sa.Column("correlation_id", sa.String(64), nullable=True))
    op.add_column("action_execution_logs", sa.Column("event_id", sa.BigInteger(), nullable=True))
    op.add_column("action_execution_logs", sa.Column("correlation_id", sa.String(64), nullable=True))
    op.create_foreign_key(
        "fk_action_execution_logs_event_id",
        "action_execution_logs",
        "ai_message_events",
        ["event_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_ai_message_events_correlation_id", "ai_message_events", ["correlation_id"])
    op.create_index("idx_action_execution_logs_event_id", "action_execution_logs", ["event_id", "created_at"])
    op.create_unique_constraint(
        "uq_ai_moderation_decision_delivery",
        "ai_moderation_decisions",
        ["event_id", "policy_version", "decision_action", "created_at"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_ai_moderation_decision_delivery", "ai_moderation_decisions", type_="unique")
    op.drop_index("idx_action_execution_logs_event_id", table_name="action_execution_logs")
    op.drop_index("idx_ai_message_events_correlation_id", table_name="ai_message_events")
    op.drop_constraint("fk_action_execution_logs_event_id", "action_execution_logs", type_="foreignkey")
    op.drop_column("action_execution_logs", "correlation_id")
    op.drop_column("action_execution_logs", "event_id")
    op.drop_column("ai_feedback_labels", "correlation_id")
    op.drop_column("ai_message_events", "correlation_id")

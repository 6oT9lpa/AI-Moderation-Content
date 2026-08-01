from datetime import datetime

from psycopg.types.json import Jsonb

from src.domain.action.action_execution_status import ActionExecutionStatus
from src.domain.api.moderation_event_repository import ModerationEventRepository
from src.domain.api.stored_moderation_event import StoredModerationEvent
from src.domain.dataset.feedback_type import FeedbackType
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.moderation.moderation_label import ModerationLabel
from src.infrastructure.database.connection import DatabaseConnection


class PostgresqlModerationEventRepository(ModerationEventRepository):
    def __init__(self, database: DatabaseConnection) -> None:
        self._database = database

    async def save_request_lineage(self, event_id: int, correlation_id: str) -> None:
        await self._database.execute(
            "UPDATE ai_message_events SET correlation_id = %s WHERE id = %s",
            [correlation_id, event_id],
        )

    async def find_event(
        self,
        event_id: int | None,
        message_id: str | None,
        guild_id: str | None,
    ) -> StoredModerationEvent | None:
        if event_id is not None:
            row = await self._database.fetch_one(
                """
                SELECT event.id, event.guild_id, event.message_id,
                       decision.id AS decision_id, decision.decision_action
                FROM ai_message_events AS event
                JOIN LATERAL (
                    SELECT id, decision_action FROM ai_moderation_decisions
                    WHERE event_id = event.id ORDER BY created_at DESC LIMIT 1
                ) AS decision ON TRUE
                WHERE event.id = %s
                """,
                [event_id],
            )
        else:
            row = await self._database.fetch_one(
                """
                SELECT event.id, event.guild_id, event.message_id,
                       decision.id AS decision_id, decision.decision_action
                FROM ai_message_events AS event
                JOIN LATERAL (
                    SELECT id, decision_action FROM ai_moderation_decisions
                    WHERE event_id = event.id ORDER BY created_at DESC LIMIT 1
                ) AS decision ON TRUE
                WHERE event.message_id = %s AND event.guild_id = %s
                ORDER BY event.processed_at DESC LIMIT 1
                """,
                [message_id, guild_id],
            )
        if row is None:
            return None
        return StoredModerationEvent(
            event_id=int(row["id"]),
            decision_id=int(row["decision_id"]),
            guild_id=str(row["guild_id"]),
            message_id=str(row["message_id"]),
            decision_action=ModerationAction(str(row["decision_action"])),
        )

    async def save_feedback(
        self,
        event: StoredModerationEvent,
        feedback_type: FeedbackType,
        labels: tuple[ModerationLabel, ...],
        primary_label: ModerationLabel | None,
        severity: int | None,
        recommended_action: ModerationAction | None,
        moderator_id: str | None,
        annotation_source: str | None,
        notes: str | None,
        idempotency_key: str | None,
        correlation_id: str,
    ) -> bool:
        result = await self._database.execute(
            """
            INSERT INTO ai_feedback_labels (
                event_id, decision_id, labels_json, primary_label, severity,
                recommended_action, moderator_id, feedback_type,
                annotation_source, notes, idempotency_key, correlation_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING
            """,
            [
                event.event_id,
                event.decision_id,
                Jsonb([label.value for label in labels]),
                primary_label.value if primary_label else None,
                severity,
                recommended_action.value if recommended_action else None,
                moderator_id,
                feedback_type.value,
                annotation_source,
                notes,
                idempotency_key,
                correlation_id,
            ],
        )
        return result.rowcount > 0

    async def save_action_result(
        self,
        event: StoredModerationEvent,
        action: ModerationAction,
        status: ActionExecutionStatus,
        dry_run: bool,
        error: str | None,
        timestamp: datetime,
        correlation_id: str,
    ) -> None:
        await self._database.execute(
            """
            INSERT INTO action_execution_logs (
                event_id, message_id, decision_action, action, status, dry_run, error,
                created_at, platform_response_json, correlation_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                event.event_id,
                event.message_id,
                event.decision_action.value,
                action.value,
                status.value,
                dry_run,
                error,
                timestamp,
                Jsonb({}),
                correlation_id,
            ],
        )

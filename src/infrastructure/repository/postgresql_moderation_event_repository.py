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

    async def find_event(self, event_id: int | None, message_id: str | None) -> StoredModerationEvent | None:
        if event_id is not None:
            row = await self._database.fetch_one(
                """
                SELECT event.id, event.message_id, decision.decision_action
                FROM ai_message_events AS event
                JOIN LATERAL (
                    SELECT decision_action FROM ai_moderation_decisions
                    WHERE event_id = event.id ORDER BY created_at DESC LIMIT 1
                ) AS decision ON TRUE
                WHERE event.id = %s
                """,
                [event_id],
            )
        else:
            row = await self._database.fetch_one(
                """
                SELECT event.id, event.message_id, decision.decision_action
                FROM ai_message_events AS event
                JOIN LATERAL (
                    SELECT decision_action FROM ai_moderation_decisions
                    WHERE event_id = event.id ORDER BY created_at DESC LIMIT 1
                ) AS decision ON TRUE
                WHERE event.message_id = %s
                ORDER BY event.processed_at DESC LIMIT 1
                """,
                [message_id],
            )
        if row is None:
            return None
        return StoredModerationEvent(
            event_id=int(row["id"]),
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
    ) -> None:
        await self._database.execute(
            """
            INSERT INTO ai_feedback_labels (
                event_id, labels_json, primary_label, severity, recommended_action,
                moderator_id, feedback_type, annotation_source, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                event.event_id,
                Jsonb([label.value for label in labels]),
                primary_label.value if primary_label else None,
                severity,
                recommended_action.value if recommended_action else None,
                moderator_id,
                feedback_type.value,
                annotation_source,
                notes,
            ],
        )

    async def save_action_result(
        self,
        event: StoredModerationEvent,
        action: ModerationAction,
        status: ActionExecutionStatus,
        dry_run: bool,
        error: str | None,
        timestamp: datetime,
    ) -> None:
        await self._database.execute(
            """
            INSERT INTO action_execution_logs (
                message_id, decision_action, action, status, dry_run, error, created_at, platform_response_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                event.message_id,
                event.decision_action.value,
                action.value,
                status.value,
                dry_run,
                error,
                timestamp,
                Jsonb({}),
            ],
        )

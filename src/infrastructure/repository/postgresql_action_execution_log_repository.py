from __future__ import annotations

from psycopg.types.json import Jsonb

from src.domain.action.action_execution_log_repository import ActionExecutionLogRepository
from src.domain.dto.action.action_execution_plan_result import ActionExecutionPlanResult
from src.domain.dto.action.action_execution_request import ActionExecutionRequest
from src.infrastructure.database.connection import DatabaseConnection
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class PostgresqlActionExecutionLogRepository(ActionExecutionLogRepository):
    def __init__(self, database: DatabaseConnection) -> None:
        self._database = database

    async def save_plan_result(
        self,
        request: ActionExecutionRequest,
        result: ActionExecutionPlanResult,
    ) -> None:
        for step in result.steps:
            await self._database.execute(
                """
                INSERT INTO action_execution_logs (
                    message_id,
                    decision_action,
                    action,
                    status,
                    dry_run,
                    reason,
                    platform,
                    guild_id,
                    channel_id,
                    user_id,
                    error,
                    platform_response_json,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    result.message_id,
                    result.decision_action.value,
                    step.action.value,
                    step.status.value,
                    result.dry_run,
                    step.reason,
                    request.platform,
                    request.guild_id or request.chat_id,
                    request.channel_id,
                    request.user_id,
                    step.error,
                    Jsonb(step.platform_response),
                    step.finished_at or result.created_at,
                ],
            )

        logger.info(
            "Action execution logs saved message_id=%s steps=%s",
            result.message_id,
            len(result.steps),
        )

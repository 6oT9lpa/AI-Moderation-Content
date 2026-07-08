from __future__ import annotations

from src.domain.dto.action.action_execution_request import ActionExecutionRequest
from src.domain.dto.action.action_execution_result import ActionExecutionResult
from src.domain.action.action_execution_status import ActionExecutionStatus
from src.infrastructure.logging.logger import get_logger
from src.modules.action.platform_action_client import PlatformActionClient

logger = get_logger(__name__)


class StubPlatformActionClient(PlatformActionClient):
    async def delete_message(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        return self._success("DELETE", request)

    async def warn_user(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        return self._success("WARN", request)

    async def timeout_user(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        return self._success("TIMEOUT", request)

    async def ban_user(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        return self._success("BAN", request)

    async def create_review(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        return self._success("REVIEW", request)

    async def log_action(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        return self._success("LOG", request)

    def _success(self, action: str, request: ActionExecutionRequest) -> ActionExecutionResult:
        logger.info(
            "Stub platform action action=%s platform=%s message_id=%s user_id=%s",
            action,
            request.platform,
            request.message_id,
            request.user_id,
        )
        return ActionExecutionResult(
            status=ActionExecutionStatus.SUCCESS,
            platform_response={"stub": True, "action": action},
        )

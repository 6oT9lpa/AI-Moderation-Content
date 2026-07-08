from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.dto.action.action_execution_plan_result import ActionExecutionPlanResult
from src.domain.dto.action.action_execution_request import ActionExecutionRequest


class ActionExecutionLogRepository(ABC):
    @abstractmethod
    async def save_plan_result(
        self,
        request: ActionExecutionRequest,
        result: ActionExecutionPlanResult,
    ) -> None:
        raise NotImplementedError

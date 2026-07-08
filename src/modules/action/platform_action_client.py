from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.dto.action.action_execution_request import ActionExecutionRequest
from src.domain.dto.action.action_execution_result import ActionExecutionResult


class PlatformActionClient(ABC):
    @abstractmethod
    async def delete_message(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        raise NotImplementedError

    @abstractmethod
    async def warn_user(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        raise NotImplementedError

    @abstractmethod
    async def timeout_user(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        raise NotImplementedError

    @abstractmethod
    async def ban_user(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        raise NotImplementedError

    @abstractmethod
    async def create_review(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        raise NotImplementedError

    @abstractmethod
    async def log_action(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        raise NotImplementedError

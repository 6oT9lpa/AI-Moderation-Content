from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.action.action_execution_status import ActionExecutionStatus


class ActionExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ActionExecutionStatus
    platform_response: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.action.action_execution_status import ActionExecutionStatus
from src.domain.moderation.moderation_action import ModerationAction


class ActionExecutionStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: ModerationAction
    status: ActionExecutionStatus
    reason: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    platform_response: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

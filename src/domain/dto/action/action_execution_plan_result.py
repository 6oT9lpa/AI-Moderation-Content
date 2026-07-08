from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from src.domain.action.action_execution_status import ActionExecutionStatus
from src.domain.dto.action.action_execution_step import ActionExecutionStep
from src.domain.moderation.moderation_action import ModerationAction


class ActionExecutionPlanResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    message_id: str
    decision_action: ModerationAction
    executed_actions: list[ModerationAction] = Field(default_factory=list)
    status: ActionExecutionStatus
    dry_run: bool
    steps: list[ActionExecutionStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.moderation.moderation_action import ModerationAction


class ModerationActionPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    primary_action: ModerationAction
    actions: list[ModerationAction] = Field(default_factory=list)
    required_actions: list[ModerationAction] = Field(default_factory=list)
    reason: str

    @model_validator(mode="after")
    def validate_action_plan(self) -> "ModerationActionPlan":
        if not self.actions:
            raise ValueError("Action plan must contain at least one action")

        for action in self.required_actions:
            if action not in self.actions:
                raise ValueError("Required actions must be included in action plan")

        return self

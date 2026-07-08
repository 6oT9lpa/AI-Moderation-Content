from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.action.retry_policy import RetryPolicy
from src.domain.moderation.moderation_action import ModerationAction


class ActionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = "default_action_policy"
    version: str = "1.0.0"
    enabled: bool = True
    dry_run: bool = True
    allowed_actions: list[ModerationAction] = Field(default_factory=list)
    destructive_actions: list[ModerationAction] = Field(default_factory=list)
    require_review_for_actions: list[ModerationAction] = Field(default_factory=list)
    action_timeouts: dict[ModerationAction, float] = Field(default_factory=dict)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    platform_overrides: dict[str, dict[str, object]] = Field(default_factory=dict)

    @field_validator("allowed_actions", "destructive_actions", "require_review_for_actions")
    @classmethod
    def deduplicate_actions(cls, value: list[ModerationAction]) -> list[ModerationAction]:
        unique_actions: list[ModerationAction] = []
        seen_actions: set[ModerationAction] = set()

        for action in value:
            if action in seen_actions:
                continue

            unique_actions.append(action)
            seen_actions.add(action)

        return unique_actions

    def is_allowed(self, action: ModerationAction) -> bool:
        return action in self.allowed_actions

    def requires_review(self, action: ModerationAction) -> bool:
        return action in self.require_review_for_actions

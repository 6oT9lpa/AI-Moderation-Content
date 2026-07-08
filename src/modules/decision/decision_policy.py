from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.decision.moderation_mode import ModerationMode
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.moderation.moderation_label import ModerationLabel
from src.modules.decision.action_threshold_policy import ActionThresholdPolicy


class DecisionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str
    version: str
    mode: ModerationMode = ModerationMode.ACTIVE
    dry_run: bool = False
    action_thresholds: ActionThresholdPolicy = Field(default_factory=ActionThresholdPolicy)
    min_confidence_for_action: float = Field(default=0.6, ge=0.0, le=1.0)
    label_overrides: dict[str, ModerationAction] = Field(default_factory=dict)
    action_bundles: dict[ModerationAction, list[ModerationAction]] = Field(default_factory=dict)
    action_priority: list[ModerationAction] = Field(default_factory=list)
    strict_mode_adjustments: dict[str, Any] = Field(default_factory=dict)
    passive_mode_adjustments: dict[str, Any] = Field(default_factory=dict)
    review_on_model_disagreement: bool = True
    review_on_low_confidence_high_risk: bool = True

    @field_validator("label_overrides")
    @classmethod
    def validate_label_overrides(cls, value: dict[str, ModerationAction]) -> dict[str, ModerationAction]:
        for label in value:
            ModerationLabel(label)

        return value

    @field_validator("action_bundles")
    @classmethod
    def validate_action_bundles(
        cls,
        value: dict[ModerationAction, list[ModerationAction]],
    ) -> dict[ModerationAction, list[ModerationAction]]:
        normalized_bundles: dict[ModerationAction, list[ModerationAction]] = {}

        for primary_action, bundled_actions in value.items():
            if not bundled_actions:
                raise ValueError(f"Action bundle for {primary_action} must not be empty")

            unique_actions: list[ModerationAction] = []
            seen_actions: set[ModerationAction] = set()

            for action in bundled_actions:
                if action in seen_actions:
                    continue

                unique_actions.append(action)
                seen_actions.add(action)

            normalized_bundles[primary_action] = unique_actions

        return normalized_bundles

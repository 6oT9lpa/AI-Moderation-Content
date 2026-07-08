from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.domain.decision.moderation_mode import ModerationMode
from src.domain.moderation.moderation_action import ModerationAction
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
    action_priority: list[ModerationAction] = Field(default_factory=list)
    strict_mode_adjustments: dict[str, Any] = Field(default_factory=dict)
    passive_mode_adjustments: dict[str, Any] = Field(default_factory=dict)
    review_on_model_disagreement: bool = True
    review_on_low_confidence_high_risk: bool = True

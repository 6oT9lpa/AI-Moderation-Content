from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.domain.decision.moderation_action_plan import ModerationActionPlan
from src.domain.decision.moderation_mode import ModerationMode
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.rule_evaluation_result import RuleEvaluationResult


class ModerationDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    message_id: str
    labels: list[ModerationLabel]
    primary_label: ModerationLabel
    risk_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    severity: int = Field(ge=0, le=5)
    decision_action: ModerationAction
    action_plan: ModerationActionPlan
    action_required: bool
    dry_run: bool
    reason: str
    rule_evaluation: RuleEvaluationResult
    policy_id: str
    policy_version: str
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.model_agreement import ModelAgreement
from src.domain.rules.moderation_signal import ModerationSignal
from src.domain.rules.risk_breakdown_item import RiskBreakdownItem


class RuleEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    signals: list[ModerationSignal]
    labels: list[ModerationLabel]
    primary_label: ModerationLabel
    confidence: float = Field(ge=0.0, le=1.0)
    severity: int = Field(ge=0, le=5)
    risk_score: float = Field(ge=0.0, le=100.0)
    risk_breakdown: list[RiskBreakdownItem]
    matched_rules: list[str]
    conflicts: list[str]
    model_agreement: ModelAgreement
    user_risk_multiplier: float = Field(default=1.0, ge=1.0)
    policy_id: str
    policy_version: str
    created_at: datetime = Field(default_factory=datetime.now)

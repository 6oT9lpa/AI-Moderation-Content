from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.signal_source import SignalSource


class RiskBreakdownItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: ModerationLabel
    source: SignalSource
    contribution: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    severity: int = Field(ge=0, le=5)
    risk_weight: int = Field(ge=0)
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)

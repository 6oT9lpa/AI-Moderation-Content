from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.signal_source import SignalSource


class ModerationSignal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: SignalSource
    label: ModerationLabel
    confidence: float = Field(ge=0.0, le=1.0)
    severity: int = Field(ge=0, le=5)
    risk_weight: int = Field(ge=0)
    evidence: dict[str, Any] = Field(default_factory=dict)
    reason: str
    rule_id: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return v

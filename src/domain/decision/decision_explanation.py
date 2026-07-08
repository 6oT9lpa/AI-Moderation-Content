from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class DecisionExplanation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action_source: str
    matched_threshold: Optional[float] = None
    matched_override: Optional[str] = None
    explanation: str
    evidence: dict[str, Any] = Field(default_factory=dict)

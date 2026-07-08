from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.signal_source import SignalSource


class ModelDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model_name: str
    model_version: str
    source: SignalSource
    labels: list[ModerationLabel]
    primary_label: ModerationLabel
    confidence: float = Field(ge=0.0, le=1.0)
    raw_output: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = Field(ge=0.0)

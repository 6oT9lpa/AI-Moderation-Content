from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.domain.rules.signal_source import SignalSource


class ModelAgreement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    agreeing_sources: list[SignalSource]
    disagreeing_sources: list[SignalSource]
    agreement_score: float = Field(ge=0.0)
    disagreement_reason: str = ""
    high_confidence_disagreement: bool = False

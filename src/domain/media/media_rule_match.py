from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.signal_source import SignalSource


@dataclass(slots=True, frozen=True)
class MediaRuleMatch:
    rule_id: str
    source: SignalSource
    labels: tuple[ModerationLabel, ...]
    severity: int
    confidence: float
    risk_weight: int
    reason: str
    evidence: dict[str, Any]

    def __post_init__(self) -> None:
        if not 0 <= self.severity <= 5:
            raise ValueError("severity must be between 0 and 5")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.risk_weight < 0:
            raise ValueError("risk_weight must be greater than or equal to 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "source": self.source.value,
            "labels": [label.value for label in self.labels],
            "severity": self.severity,
            "confidence": self.confidence,
            "risk_weight": self.risk_weight,
            "reason": self.reason,
            "evidence": self.evidence,
        }

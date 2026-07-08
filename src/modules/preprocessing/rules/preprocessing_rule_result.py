from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.domain.moderation.moderation_label import ModerationLabel


@dataclass(slots=True, frozen=True)
class PreprocessingRuleResult:
    rule_id: str
    labels: tuple[ModerationLabel, ...]
    severity: int
    confidence: float
    reason: str
    risk_weight: int = 0
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "labels": [label.value for label in self.labels],
            "severity": self.severity,
            "confidence": self.confidence,
            "reason": self.reason,
            "risk_weight": self.risk_weight,
            "evidence": self.evidence,
        }

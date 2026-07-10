from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class MediaRiskResult:
    score: int
    breakdown: tuple[tuple[str, int], ...]
    requires_review: bool
    high_risk: bool

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "breakdown": [
                {"reason": reason, "score": score}
                for reason, score in self.breakdown
            ],
            "requires_review": self.requires_review,
            "high_risk": self.high_risk,
        }

from __future__ import annotations

from src.domain.rules.moderation_signal import ModerationSignal
from src.domain.rules.risk_breakdown_item import RiskBreakdownItem
from src.modules.rules.risk_score_calculator import RiskScoreCalculator
from src.contracts.rules.moderation_rule_policy import ModerationRulePolicy


class RiskBreakdownBuilder:
    def __init__(self, calculator: RiskScoreCalculator):
        self._calculator = calculator

    def build(
        self, signals: list[ModerationSignal], policy: ModerationRulePolicy
    ) -> list[RiskBreakdownItem]:
        breakdown = []
        for signal in signals:
            contribution = self._calculator.calculate_contribution(signal, policy)
            item = RiskBreakdownItem(
                label=signal.label,
                source=signal.source,
                contribution=contribution,
                confidence=signal.confidence,
                severity=signal.severity,
                risk_weight=signal.risk_weight,
                reason=signal.reason,
                evidence=signal.evidence,
            )
            breakdown.append(item)
        return breakdown

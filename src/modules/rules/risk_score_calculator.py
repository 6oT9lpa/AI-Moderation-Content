from __future__ import annotations

from src.domain.rules.moderation_signal import ModerationSignal
from src.infrastructure.logging.logger import get_logger
from src.contracts.rules.moderation_rule_policy import ModerationRulePolicy

logger = get_logger(__name__)


class RiskScoreCalculator:
    def calculate_contribution(
        self, signal: ModerationSignal, policy: ModerationRulePolicy
    ) -> float:
        source_weight = getattr(policy.source_weights, signal.source.value, 1.0)
        label_weight = max(
            getattr(policy.label_weights, signal.label.value, 10.0),
            float(signal.risk_weight),
        )
        severity_multiplier = policy.severity_multipliers.get(signal.severity, 1.0)

        contribution = (
            label_weight * source_weight * signal.confidence * severity_multiplier
        )

        logger.debug(
            "Calculated contribution source=%s label=%s contribution=%.2f label_weight=%s "
            "source_weight=%s confidence=%s severity_multiplier=%s signal_risk_weight=%s",
            signal.source,
            signal.label,
            contribution,
            label_weight,
            source_weight,
            signal.confidence,
            severity_multiplier,
            signal.risk_weight,
        )

        return contribution

    def calculate_total_score(
        self, contributions: list[float], policy: ModerationRulePolicy
    ) -> float:
        if not contributions:
            return 0.0

        total = sum(contributions)
        clamped = max(policy.risk_score.min, min(policy.risk_score.max, total))

        logger.debug("Total risk score calculated risk_score=%.2f raw_score=%.2f", clamped, total)
        return clamped

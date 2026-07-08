from __future__ import annotations

from src.domain.rules.moderation_signal import ModerationSignal
from src.infrastructure.logging.logger import get_logger
from src.modules.rules.moderation_rule_policy import ModerationRulePolicy

logger = get_logger(__name__)


class RiskScoreCalculator:
    def calculate_contribution(
        self, signal: ModerationSignal, policy: ModerationRulePolicy
    ) -> float:
        source_weight = getattr(policy.source_weights, signal.source.value, 1.0)
        label_weight = getattr(policy.label_weights, signal.label.value, 10.0)
        severity_multiplier = policy.severity_multipliers.get(signal.severity, 1.0)

        contribution = (
            label_weight * source_weight * signal.confidence * severity_multiplier
        )

        logger.debug(
            f"Calculated contribution for {signal.source}:{signal.label}: {contribution:.2f} "
            f"(label_w: {label_weight}, source_w: {source_weight}, "
            f"conf: {signal.confidence}, sev_mult: {severity_multiplier})"
        )

        return contribution

    def calculate_total_score(
        self, contributions: list[float], policy: ModerationRulePolicy
    ) -> float:
        if not contributions:
            return 0.0

        # Simple sum for now, clamped to policy limits
        total = sum(contributions)
        clamped = max(policy.risk_score.min, min(policy.risk_score.max, total))

        logger.debug(f"Total risk score: {clamped:.2f} (raw: {total:.2f})")
        return clamped

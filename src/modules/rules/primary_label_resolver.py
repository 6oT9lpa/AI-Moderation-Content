from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.risk_breakdown_item import RiskBreakdownItem
from src.domain.rules.signal_source import SignalSource
from src.infrastructure.logging.logger import get_logger
from src.contracts.rules.moderation_rule_policy import ModerationRulePolicy

logger = get_logger(__name__)

_MODEL_PRIMARY_BONUS = {
    SignalSource.RUBERT: 6.0,
    SignalSource.QWEN: 8.0,
}
_MODEL_PRIMARY_MIN_CONFIDENCE = 0.8


class PrimaryLabelResolver:
    def resolve(
        self, breakdown: list[RiskBreakdownItem], policy: ModerationRulePolicy
    ) -> ModerationLabel:
        if not breakdown:
            return ModerationLabel.SAFE

        priority_map = {label: i for i, label in enumerate(policy.primary_label_priority)}
        priority_count = len(policy.primary_label_priority)

        def score(item: RiskBreakdownItem) -> tuple[float, int, int, float]:
            priority_bonus = max(priority_count - priority_map.get(item.label, priority_count), 0)
            model_bonus = self._model_primary_bonus(item)
            return (
                item.contribution + (priority_bonus * 0.5) + model_bonus,
                item.severity,
                priority_bonus,
                item.confidence,
            )

        sorted_items = sorted(breakdown, key=score, reverse=True)
        primary = sorted_items[0].label

        logger.debug("Resolved primary label label=%s", primary)
        return primary

    @staticmethod
    def _model_primary_bonus(item: RiskBreakdownItem) -> float:
        if item.label == ModerationLabel.SAFE:
            return 0.0
        if item.confidence < _MODEL_PRIMARY_MIN_CONFIDENCE:
            return 0.0
        return _MODEL_PRIMARY_BONUS.get(item.source, 0.0)

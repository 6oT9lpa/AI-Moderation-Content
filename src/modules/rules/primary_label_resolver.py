from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.risk_breakdown_item import RiskBreakdownItem
from src.infrastructure.logging.logger import get_logger
from src.modules.rules.moderation_rule_policy import ModerationRulePolicy

logger = get_logger(__name__)


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
            return (
                item.contribution + (priority_bonus * 0.5),
                item.severity,
                priority_bonus,
                item.confidence,
            )

        sorted_items = sorted(breakdown, key=score, reverse=True)
        primary = sorted_items[0].label

        logger.debug("Resolved primary label label=%s", primary)
        return primary

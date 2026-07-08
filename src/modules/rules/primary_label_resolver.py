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

        # Sort by priority from policy, then by contribution
        priority_map = {label: i for i, label in enumerate(policy.primary_label_priority)}

        def sort_key(item: RiskBreakdownItem):
            # Lower index in priority_map means higher priority
            priority = priority_map.get(item.label, 999)
            return (priority, -item.contribution, -item.confidence)

        sorted_items = sorted(breakdown, key=sort_key)
        primary = sorted_items[0].label

        logger.debug(f"Resolved primary label: {primary}")
        return primary

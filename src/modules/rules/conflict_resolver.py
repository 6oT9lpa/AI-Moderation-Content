from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.moderation_signal import ModerationSignal
from src.infrastructure.logging.logger import get_logger
from src.contracts.rules.moderation_rule_policy import ModerationRulePolicy

logger = get_logger(__name__)


class ConflictResolver:
    def resolve(
        self,
        signals: list[ModerationSignal],
        primary_label: ModerationLabel,
        policy: ModerationRulePolicy,
    ) -> tuple[ModerationLabel, list[str]]:
        conflicts = []
        resolved_label = primary_label

        labels = {s.label for s in signals}

        if ModerationLabel.SAFE in labels and len(labels) > 1:
            conflicts.append(f"safe_mixed_signals: SAFE present with harmful labels: {labels - {ModerationLabel.SAFE}}")

            if resolved_label == ModerationLabel.SAFE:
                harmful_labels = self._sort_by_priority(
                    [label for label in labels if label != ModerationLabel.SAFE],
                    policy,
                )

                if harmful_labels:
                    resolved_label = harmful_labels[0]
                    conflicts.append("safe_conflict: SAFE excluded from primary due to harmful signals")

        if ModerationLabel.URL in labels and ModerationLabel.SCAM in labels:
            if resolved_label == ModerationLabel.URL:
                resolved_label = ModerationLabel.SCAM
                conflicts.append("url_scam_conflict: SCAM preferred over URL")

        if conflicts:
            logger.info("Conflicts resolved conflicts=%s primary_label=%s", conflicts, resolved_label)

        return resolved_label, conflicts

    def _sort_by_priority(
        self,
        labels: list[ModerationLabel],
        policy: ModerationRulePolicy,
    ) -> list[ModerationLabel]:
        priority_map = {label: index for index, label in enumerate(policy.primary_label_priority)}
        return sorted(labels, key=lambda label: priority_map.get(label, 999))

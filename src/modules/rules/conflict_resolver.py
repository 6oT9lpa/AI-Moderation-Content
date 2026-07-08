from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.moderation_signal import ModerationSignal
from src.infrastructure.logging.logger import get_logger
from src.modules.rules.moderation_rule_policy import ModerationRulePolicy

logger = get_logger(__name__)


class ConflictResolver:
    def resolve(
        self, 
        signals: list[ModerationSignal], 
        primary_label: ModerationLabel, 
        policy: ModerationRulePolicy
    ) -> tuple[ModerationLabel, list[str]]:
        conflicts = []
        resolved_label = primary_label

        labels = {s.label for s in signals}

        # Rule: SAFE + harmful labels -> SAFE not primary
        if ModerationLabel.SAFE in labels and len(labels) > 1:
            conflicts.append(f"safe_mixed_signals: SAFE present with harmful labels: {labels - {ModerationLabel.SAFE}}")
            if resolved_label == ModerationLabel.SAFE:
                # Find next best label
                harmful_labels = [l for l in labels if l != ModerationLabel.SAFE]
                if harmful_labels:
                    resolved_label = harmful_labels[0]
                    conflicts.append("safe_conflict: SAFE excluded from primary due to harmful signals")

        # Rule: URL + SCAM -> SCAM primary
        if ModerationLabel.URL in labels and ModerationLabel.SCAM in labels:
            if resolved_label == ModerationLabel.URL:
                resolved_label = ModerationLabel.SCAM
                conflicts.append("url_scam_conflict: SCAM preferred over URL")

        if conflicts:
            logger.info(f"Conflicts resolved: {conflicts}. New primary: {resolved_label}")

        return resolved_label, conflicts

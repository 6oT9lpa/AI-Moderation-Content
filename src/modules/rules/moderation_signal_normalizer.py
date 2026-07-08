from __future__ import annotations

from src.domain.rules.moderation_signal import ModerationSignal
from src.infrastructure.logging.logger import get_logger
from src.modules.rules.moderation_rule_policy import ModerationRulePolicy

logger = get_logger(__name__)


class ModerationSignalNormalizer:
    def normalize(
        self, signals: list[ModerationSignal], policy: ModerationRulePolicy
    ) -> list[ModerationSignal]:
        logger.debug(f"Normalizing {len(signals)} signals")

        filtered_signals = []
        for signal in signals:
            if self._should_filter(signal, policy):
                logger.debug(
                    f"Signal filtered: {signal.source}:{signal.label} "
                    f"(conf: {signal.confidence})"
                )
                continue
            filtered_signals.append(signal)

        return filtered_signals

    def _should_filter(self, signal: ModerationSignal, policy: ModerationRulePolicy) -> bool:
        thresholds = policy.confidence_thresholds

        # Check per-label threshold
        label_threshold = thresholds.per_label_min_confidence.get(signal.label.value)
        if label_threshold is not None and signal.confidence < label_threshold:
            return True

        # Check per-source threshold
        source_threshold = thresholds.per_source_min_confidence.get(signal.source.value)
        if source_threshold is not None and signal.confidence < source_threshold:
            return True

        # Check default threshold
        if signal.confidence < thresholds.default_min_confidence:
            return True

        return False

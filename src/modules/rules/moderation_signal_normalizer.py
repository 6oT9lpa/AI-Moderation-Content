from __future__ import annotations

from src.domain.rules.moderation_signal import ModerationSignal
from src.infrastructure.logging.logger import get_logger
from src.contracts.rules.moderation_rule_policy import ModerationRulePolicy

logger = get_logger(__name__)


class ModerationSignalNormalizer:
    def normalize(
        self, signals: list[ModerationSignal], policy: ModerationRulePolicy
    ) -> list[ModerationSignal]:
        logger.debug("Normalizing moderation signals count=%s", len(signals))

        filtered_signals = []
        for signal in signals:
            if self._should_filter(signal, policy):
                logger.debug(
                    "Moderation signal filtered source=%s label=%s confidence=%s",
                    signal.source,
                    signal.label,
                    signal.confidence,
                )
                continue
            filtered_signals.append(signal)

        return filtered_signals

    def _should_filter(self, signal: ModerationSignal, policy: ModerationRulePolicy) -> bool:
        thresholds = policy.confidence_thresholds
        selected_threshold = thresholds.default_min_confidence

        label_threshold = thresholds.per_label_min_confidence.get(signal.label.value)
        source_threshold = thresholds.per_source_min_confidence.get(signal.source.value)

        if source_threshold is not None:
            selected_threshold = source_threshold

        if label_threshold is not None:
            selected_threshold = label_threshold

        return signal.confidence < selected_threshold

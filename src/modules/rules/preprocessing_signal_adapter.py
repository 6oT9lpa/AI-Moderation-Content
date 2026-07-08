from __future__ import annotations

from typing import Any

from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.moderation_signal import ModerationSignal
from src.domain.rules.signal_source import SignalSource
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class PreprocessingSignalAdapter:
    def adapt(self, data: dict[str, Any]) -> list[ModerationSignal]:
        logger.debug("Adapting preprocessing result rule_id=%s", data.get("rule_id"))

        rule_id = data.get("rule_id", "unknown")
        labels = data.get("labels", [])
        confidence = data.get("confidence", 0.0)
        severity = data.get("severity", 0)
        risk_weight = data.get("risk_weight", 0)
        evidence = data.get("evidence", {})
        reason = data.get("reason", "")

        signals = []
        for label_val in labels:
            try:
                label = ModerationLabel(label_val)
                signal = ModerationSignal(
                    source=SignalSource.PREPROCESSING,
                    label=label,
                    confidence=confidence,
                    severity=severity,
                    risk_weight=risk_weight,
                    evidence=evidence,
                    reason=reason,
                    rule_id=rule_id,
                )
                signals.append(signal)
            except ValueError:
                logger.warning("Unknown label in preprocessing result label=%s rule_id=%s", label_val, rule_id)

        return signals

from __future__ import annotations

from src.domain.media.media_rule_match import MediaRuleMatch
from src.domain.rules.moderation_signal import ModerationSignal
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class MediaSignalAdapter:
    def adapt(self, match: MediaRuleMatch) -> list[ModerationSignal]:
        signals = [
            ModerationSignal(
                source=match.source,
                label=label,
                confidence=match.confidence,
                severity=match.severity,
                risk_weight=match.risk_weight,
                evidence=match.evidence,
                reason=match.reason,
                rule_id=match.rule_id,
            )
            for label in match.labels
        ]
        logger.info("Media rule adapted rule_id=%s signal_count=%s", match.rule_id, len(signals))
        return signals

from __future__ import annotations

from src.domain.rules.model_agreement import ModelAgreement
from src.domain.rules.moderation_signal import ModerationSignal
from src.domain.rules.signal_source import SignalSource
from src.infrastructure.logging.logger import get_logger
from src.modules.rules.moderation_rule_policy import ModerationRulePolicy

logger = get_logger(__name__)


class ModelAgreementCalculator:
    def calculate(
        self, signals: list[ModerationSignal], policy: ModerationRulePolicy
    ) -> ModelAgreement:
        if not policy.model_agreement.enabled:
            return ModelAgreement(
                agreeing_sources=[],
                disagreeing_sources=[],
                agreement_score=1.0,
            )

        # Filter high confidence signals from models
        model_sources = {SignalSource.RUBERT, SignalSource.QWEN}
        model_signals = [
            s for s in signals 
            if s.source in model_sources and s.confidence >= policy.model_agreement.high_confidence_threshold
        ]

        if not model_signals:
            return ModelAgreement(
                agreeing_sources=[],
                disagreeing_sources=[],
                agreement_score=1.0,
            )

        # Check if they agree on the same label
        labels_by_source = {}
        for s in model_signals:
            labels_by_source[s.source] = s.label

        sources = list(labels_by_source.keys())
        if len(sources) < 2:
            return ModelAgreement(
                agreeing_sources=sources,
                disagreeing_sources=[],
                agreement_score=1.0,
            )

        # Compare first two for simplicity (can be extended)
        s1, s2 = sources[0], sources[1]
        if labels_by_source[s1] == labels_by_source[s2]:
            return ModelAgreement(
                agreeing_sources=[s1, s2],
                disagreeing_sources=[],
                agreement_score=1.0 + policy.model_agreement.agreement_bonus,
            )
        else:
            return ModelAgreement(
                agreeing_sources=[],
                disagreeing_sources=[s1, s2],
                agreement_score=1.0 - policy.model_agreement.disagreement_penalty,
                disagreement_reason=f"Models {s1} and {s2} disagreed on labels: {labels_by_source[s1]} vs {labels_by_source[s2]}",
                high_confidence_disagreement=True,
            )

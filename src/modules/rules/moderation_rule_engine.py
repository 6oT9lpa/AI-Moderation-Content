from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.moderation_signal import ModerationSignal
from src.domain.rules.rule_evaluation_result import RuleEvaluationResult
from src.infrastructure.logging.logger import get_logger
from src.modules.rules.conflict_resolver import ConflictResolver
from src.modules.rules.model_agreement_calculator import ModelAgreementCalculator
from src.modules.rules.moderation_rule_policy import ModerationRulePolicy
from src.modules.rules.moderation_rule_policy_config_loader import (
    ModerationRulePolicyConfigLoader,
)
from src.modules.rules.moderation_signal_normalizer import ModerationSignalNormalizer
from src.modules.rules.primary_label_resolver import PrimaryLabelResolver
from src.modules.rules.risk_breakdown_builder import RiskBreakdownBuilder
from src.modules.rules.risk_score_calculator import RiskScoreCalculator

logger = get_logger(__name__)


class ModerationRuleEngine:
    def __init__(
        self,
        policy: Optional[ModerationRulePolicy] = None,
        normalizer: Optional[ModerationSignalNormalizer] = None,
        calculator: Optional[RiskScoreCalculator] = None,
        breakdown_builder: Optional[RiskBreakdownBuilder] = None,
        label_resolver: Optional[PrimaryLabelResolver] = None,
        conflict_resolver: Optional[ConflictResolver] = None,
        agreement_calculator: Optional[ModelAgreementCalculator] = None,
    ):
        self._policy = policy or ModerationRulePolicyConfigLoader.load()
        self._normalizer = normalizer or ModerationSignalNormalizer()
        self._calculator = calculator or RiskScoreCalculator()
        self._breakdown_builder = breakdown_builder or RiskBreakdownBuilder(self._calculator)
        self._label_resolver = label_resolver or PrimaryLabelResolver()
        self._conflict_resolver = conflict_resolver or ConflictResolver()
        self._agreement_calculator = agreement_calculator or ModelAgreementCalculator()

    def evaluate(
        self, message_id: str, signals: list[ModerationSignal], policy: Optional[ModerationRulePolicy] = None
    ) -> RuleEvaluationResult:
        current_policy = policy or self._policy
        
        logger.info(f"Rule Engine evaluation started for message {message_id} with {len(signals)} signals")

        # 1. Normalize and filter signals
        normalized_signals = self._normalizer.normalize(signals, current_policy)
        
        # 2. Calculate risk breakdown
        breakdown = self._breakdown_builder.build(normalized_signals, current_policy)
        
        # 3. Calculate total risk score
        contributions = [item.contribution for item in breakdown]
        risk_score = self._calculator.calculate_total_score(contributions, current_policy)
        
        # 4. Resolve primary label
        initial_primary = self._label_resolver.resolve(breakdown, current_policy)
        
        # 5. Resolve conflicts
        primary_label, conflicts = self._conflict_resolver.resolve(
            normalized_signals, initial_primary, current_policy
        )
        
        # 6. Calculate model agreement
        agreement = self._agreement_calculator.calculate(normalized_signals, current_policy)
        
        # Adjust risk score based on agreement
        risk_score = max(0.0, min(100.0, risk_score * agreement.agreement_score))

        # 7. Build result
        result = RuleEvaluationResult(
            signals=normalized_signals,
            labels=list({s.label for s in normalized_signals}) or [ModerationLabel.SAFE],
            primary_label=primary_label,
            confidence=max([s.confidence for s in normalized_signals]) if normalized_signals else 1.0,
            severity=max([s.severity for s in normalized_signals]) if normalized_signals else 0,
            risk_score=risk_score,
            risk_breakdown=breakdown,
            matched_rules=[s.rule_id for s in normalized_signals if s.rule_id],
            conflicts=conflicts,
            model_agreement=agreement,
            policy_id=current_policy.policy_id,
            policy_version=current_policy.version,
            created_at=datetime.now(),
        )

        logger.info(
            f"Rule Engine evaluation finished for {message_id}. "
            f"Primary: {result.primary_label}, Risk: {result.risk_score:.2f}"
        )
        
        return result

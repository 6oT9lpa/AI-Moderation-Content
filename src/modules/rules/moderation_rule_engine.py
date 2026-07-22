from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.domain.message_context import MessageContext
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.moderation_signal import ModerationSignal
from src.domain.rules.rule_evaluation_result import RuleEvaluationResult
from src.infrastructure.logging.logger import get_logger
from src.modules.rules.conflict_resolver import ConflictResolver
from src.modules.rules.model_agreement_calculator import ModelAgreementCalculator
from src.contracts.rules.moderation_rule_policy import ModerationRulePolicy
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
        self,
        message_id: str,
        signals: list[ModerationSignal],
        policy: Optional[ModerationRulePolicy] = None,
        context: MessageContext | None = None,
    ) -> RuleEvaluationResult:
        current_policy = policy or self._policy

        logger.info(
            "Rule Engine evaluation started message_id=%s signal_count=%s policy_id=%s policy_version=%s",
            message_id,
            len(signals),
            current_policy.policy_id,
            current_policy.version,
        )

        normalized_signals = self._normalizer.normalize(signals, current_policy)
        breakdown = self._breakdown_builder.build(normalized_signals, current_policy)
        contributions = self._aggregate_contributions_by_label(breakdown)
        risk_score = self._calculator.calculate_total_score(contributions, current_policy)
        initial_primary = self._label_resolver.resolve(breakdown, current_policy)

        primary_label, conflicts = self._conflict_resolver.resolve(
            normalized_signals, initial_primary, current_policy
        )

        agreement = self._agreement_calculator.calculate(normalized_signals, current_policy)
        user_risk_multiplier = self._user_risk_multiplier(context, current_policy)
        risk_score = max(
            current_policy.risk_score.min,
            min(current_policy.risk_score.max, risk_score * agreement.agreement_score * user_risk_multiplier),
        )
        labels = self._resolve_labels(normalized_signals, current_policy)

        result = RuleEvaluationResult(
            signals=normalized_signals,
            labels=labels,
            primary_label=primary_label,
            confidence=max([s.confidence for s in normalized_signals]) if normalized_signals else 1.0,
            severity=max([s.severity for s in normalized_signals]) if normalized_signals else 0,
            risk_score=risk_score,
            risk_breakdown=breakdown,
            matched_rules=[s.rule_id for s in normalized_signals if s.rule_id],
            conflicts=conflicts,
            model_agreement=agreement,
            user_risk_multiplier=user_risk_multiplier,
            policy_id=current_policy.policy_id,
            policy_version=current_policy.version,
            created_at=datetime.now(timezone.utc),
        )

        logger.info(
            "Rule Engine evaluation finished message_id=%s primary_label=%s risk_score=%.2f "
            "confidence=%s conflicts=%s",
            message_id,
            result.primary_label,
            result.risk_score,
            result.confidence,
            result.conflicts,
        )

        return result

    @staticmethod
    def _user_risk_multiplier(
        context: MessageContext | None,
        policy: ModerationRulePolicy,
    ) -> float:
        if context is None or not policy.user_risk.enabled:
            return 1.0

        settings = policy.user_risk
        multiplier = 1.0
        if context.account_age_days is not None and context.account_age_days < settings.new_account_days:
            multiplier *= settings.new_account_multiplier
        if context.member_age_days is not None and context.member_age_days < settings.new_member_days:
            multiplier *= settings.new_member_multiplier

        raw_count = context.metadata.get(settings.recent_violation_count_key, 0)
        try:
            recent_violations = int(raw_count)
        except (TypeError, ValueError):
            recent_violations = 0
        if recent_violations >= settings.violation_threshold:
            multiplier *= settings.repeat_violation_multiplier
        return min(multiplier, settings.max_multiplier)

    def _resolve_labels(
        self,
        signals: list[ModerationSignal],
        policy: ModerationRulePolicy,
    ) -> list[ModerationLabel]:
        if not signals:
            return [ModerationLabel.SAFE]

        labels = {signal.label for signal in signals}
        non_safe_labels = {label for label in labels if label != ModerationLabel.SAFE}
        if non_safe_labels:
            labels = non_safe_labels

        priority_map = {label: index for index, label in enumerate(policy.primary_label_priority)}
        return sorted(labels, key=lambda label: priority_map.get(label, 999))

    @staticmethod
    def _aggregate_contributions_by_label(breakdown: list) -> list[float]:
        contributions_by_label: dict[ModerationLabel, float] = {}
        for item in breakdown:
            current = contributions_by_label.get(item.label, 0.0)
            contributions_by_label[item.label] = max(current, item.contribution)
        return list(contributions_by_label.values())

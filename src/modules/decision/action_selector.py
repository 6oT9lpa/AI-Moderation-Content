from __future__ import annotations

from src.domain.decision.moderation_mode import ModerationMode
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.rules.rule_evaluation_result import RuleEvaluationResult
from src.infrastructure.logging.logger import get_logger
from src.modules.decision.decision_policy import DecisionPolicy

logger = get_logger(__name__)


class ActionSelector:
    def select(
        self, result: RuleEvaluationResult, policy: DecisionPolicy
    ) -> tuple[ModerationAction, str]:
        risk_score = self._adjust_risk_by_mode(result.risk_score, policy)
        primary_label = result.primary_label

        if policy.review_on_model_disagreement and result.model_agreement.high_confidence_disagreement:
            logger.debug("Model disagreement detected, selecting REVIEW")
            return ModerationAction.REVIEW, "Model disagreement"

        override_action = policy.label_overrides.get(primary_label.value)

        if override_action:
            logger.debug("Label override matched label=%s action=%s", primary_label, override_action)
            selected_action = override_action
            reason = f"Label override: {primary_label}"
        else:
            selected_action = self._select_by_threshold(risk_score, policy)
            reason = f"Risk score threshold: {risk_score:.2f}"

        selected_action = self._downgrade_low_confidence_action(selected_action, result, policy)
        return self._adjust_by_mode(selected_action, policy), reason

    def _select_by_threshold(self, risk_score: float, policy: DecisionPolicy) -> ModerationAction:
        thresholds = policy.action_thresholds

        if risk_score >= thresholds.BAN:
            return ModerationAction.BAN
        if risk_score >= thresholds.TIMEOUT:
            return ModerationAction.TIMEOUT
        if risk_score >= thresholds.DELETE_WARN:
            return ModerationAction.DELETE_WARN
        if risk_score >= thresholds.DELETE:
            return ModerationAction.DELETE
        if risk_score >= thresholds.WARN:
            return ModerationAction.WARN
        if risk_score >= thresholds.REVIEW:
            return ModerationAction.REVIEW
        if risk_score >= thresholds.LOG:
            return ModerationAction.LOG

        return ModerationAction.IGNORE

    def _downgrade_low_confidence_action(
        self,
        action: ModerationAction,
        result: RuleEvaluationResult,
        policy: DecisionPolicy,
    ) -> ModerationAction:
        destructive_actions = {
            ModerationAction.DELETE,
            ModerationAction.DELETE_WARN,
            ModerationAction.BAN,
            ModerationAction.TIMEOUT,
        }

        if action not in destructive_actions:
            return action

        min_confidence = self._min_confidence_for_mode(policy)

        if result.confidence >= min_confidence:
            return action

        if policy.review_on_low_confidence_high_risk:
            logger.debug(
                "Action downgraded to REVIEW reason=low_confidence action=%s confidence=%s threshold=%s",
                action,
                result.confidence,
                min_confidence,
            )
            return ModerationAction.REVIEW

        return action

    def _adjust_risk_by_mode(self, risk_score: float, policy: DecisionPolicy) -> float:
        if policy.mode != ModerationMode.STRICT:
            return risk_score

        multiplier = float(policy.strict_mode_adjustments.get("risk_multiplier", 1.0))
        adjusted_risk = min(100.0, risk_score * multiplier)
        logger.debug(
            "Strict mode risk adjusted original_risk=%s adjusted_risk=%s multiplier=%s",
            risk_score,
            adjusted_risk,
            multiplier,
        )
        return adjusted_risk

    def _min_confidence_for_mode(self, policy: DecisionPolicy) -> float:
        min_confidence = policy.min_confidence_for_action

        if policy.mode == ModerationMode.STRICT:
            reduction = float(policy.strict_mode_adjustments.get("confidence_threshold_reduction", 0.0))
            return max(0.0, min_confidence - reduction)

        return min_confidence

    def _adjust_by_mode(self, action: ModerationAction, policy: DecisionPolicy) -> ModerationAction:
        if policy.mode == ModerationMode.PASSIVE:
            max_action = ModerationAction(policy.passive_mode_adjustments.get("max_action", "REVIEW"))
            priority = {a: i for i, a in enumerate(policy.action_priority)}

            if priority.get(action, 999) < priority.get(max_action, 999):
                return max_action

        return action

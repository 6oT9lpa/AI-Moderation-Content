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
        risk_score = result.risk_score
        primary_label = result.primary_label

        # 1. Check label overrides
        override_action = policy.label_overrides.get(primary_label.value)
        if override_action:
            logger.debug(f"Label override matched for {primary_label}: {override_action}")
            return self._adjust_by_mode(override_action, policy), f"Label override: {primary_label}"

        # 2. Check model disagreement
        if policy.review_on_model_disagreement and result.model_agreement.high_confidence_disagreement:
            logger.debug("Model disagreement detected, selecting REVIEW")
            return ModerationAction.REVIEW, "Model disagreement"

        # 3. Check thresholds
        thresholds = policy.action_thresholds
        selected_action = ModerationAction.IGNORE

        # Check from highest to lowest
        if risk_score >= thresholds.BAN: selected_action = ModerationAction.BAN
        elif risk_score >= thresholds.TIMEOUT: selected_action = ModerationAction.TIMEOUT
        elif risk_score >= thresholds.DELETE_WARN: selected_action = ModerationAction.DELETE_WARN
        elif risk_score >= thresholds.DELETE: selected_action = ModerationAction.DELETE
        elif risk_score >= thresholds.WARN: selected_action = ModerationAction.WARN
        elif risk_score >= thresholds.REVIEW: selected_action = ModerationAction.REVIEW
        elif risk_score >= thresholds.LOG: selected_action = ModerationAction.LOG

        # 4. Low confidence check
        if selected_action in {ModerationAction.DELETE, ModerationAction.BAN, ModerationAction.TIMEOUT}:
            if result.confidence < policy.min_confidence_for_action:
                logger.debug(f"Confidence {result.confidence} below threshold, downgrading to REVIEW")
                selected_action = ModerationAction.REVIEW

        return self._adjust_by_mode(selected_action, policy), f"Risk score threshold: {risk_score:.2f}"

    def _adjust_by_mode(self, action: ModerationAction, policy: DecisionPolicy) -> ModerationAction:
        if policy.mode == ModerationMode.PASSIVE:
            # Passive mode: no destructive actions
            max_action = ModerationAction(policy.passive_mode_adjustments.get("max_action", "REVIEW"))
            # This is a simplified priority check
            priority = {a: i for i, a in enumerate(policy.action_priority)}
            if priority.get(action, 999) < priority.get(max_action, 999):
                return max_action
        return action

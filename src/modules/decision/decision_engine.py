"""Convert evaluated moderation evidence into a policy-governed recommendation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.domain.decision.moderation_decision import ModerationDecision
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.rules.rule_evaluation_result import RuleEvaluationResult
from src.infrastructure.logging.logger import get_logger
from src.modules.decision.action_plan_builder import ActionPlanBuilder
from src.modules.decision.action_selector import ActionSelector
from src.modules.decision.decision_policy import DecisionPolicy
from src.modules.decision.decision_policy_config_loader import (
    DecisionPolicyConfigLoader,
)

logger = get_logger(__name__)


class DecisionEngine:
    """Select one recommendation and expand it into an action bundle."""
    def __init__(
        self,
        policy: Optional[DecisionPolicy] = None,
        action_selector: Optional[ActionSelector] = None,
        action_plan_builder: Optional[ActionPlanBuilder] = None,
    ):
        self._policy = policy or DecisionPolicyConfigLoader.load()
        self._action_selector = action_selector or ActionSelector()
        self._action_plan_builder = action_plan_builder or ActionPlanBuilder()

    def decide(
        self,
        message_id: str,
        rule_evaluation: RuleEvaluationResult,
        policy: Optional[DecisionPolicy] = None,
    ) -> ModerationDecision:
        """Build an auditable recommendation; platform enforcement happens elsewhere."""
        current_policy = policy or self._policy

        logger.info(
            "Decision Engine started message_id=%s policy_id=%s policy_version=%s mode=%s dry_run=%s",
            message_id,
            current_policy.policy_id,
            current_policy.version,
            current_policy.mode,
            current_policy.dry_run,
        )

        action, reason = self._action_selector.select(rule_evaluation, current_policy)
        action_plan = self._action_plan_builder.build(action, current_policy)
        action_required = any(planned_action != ModerationAction.IGNORE for planned_action in action_plan.actions)

        decision = ModerationDecision(
            message_id=message_id,
            labels=rule_evaluation.labels,
            primary_label=rule_evaluation.primary_label,
            risk_score=rule_evaluation.risk_score,
            confidence=rule_evaluation.confidence,
            severity=rule_evaluation.severity,
            decision_action=action,
            action_plan=action_plan,
            action_required=action_required,
            dry_run=current_policy.dry_run,
            reason=reason,
            rule_evaluation=rule_evaluation,
            policy_id=current_policy.policy_id,
            policy_version=current_policy.version,
            created_at=datetime.now(timezone.utc),
            metadata={
                "mode": current_policy.mode.value,
                "dry_run": current_policy.dry_run,
            },
        )

        logger.info(
            "Decision Engine finished message_id=%s action=%s action_required=%s reason=%s",
            message_id,
            decision.decision_action,
            decision.action_required,
            decision.reason,
        )

        return decision

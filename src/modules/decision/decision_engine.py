from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.domain.decision.moderation_decision import ModerationDecision
from src.domain.rules.rule_evaluation_result import RuleEvaluationResult
from src.infrastructure.logging.logger import get_logger
from src.modules.decision.action_selector import ActionSelector
from src.modules.decision.decision_policy import DecisionPolicy
from src.modules.decision.decision_policy_config_loader import (
    DecisionPolicyConfigLoader,
)

logger = get_logger(__name__)


class DecisionEngine:
    def __init__(
        self,
        policy: Optional[DecisionPolicy] = None,
        action_selector: Optional[ActionSelector] = None,
    ):
        self._policy = policy or DecisionPolicyConfigLoader.load()
        self._action_selector = action_selector or ActionSelector()

    def decide(
        self,
        message_id: str,
        rule_evaluation: RuleEvaluationResult,
        policy: Optional[DecisionPolicy] = None,
    ) -> ModerationDecision:
        current_policy = policy or self._policy

        logger.info(f"Decision Engine started for message {message_id}")

        # 1. Select action
        action, reason = self._action_selector.select(rule_evaluation, current_policy)

        # 2. Determine if action is required
        from src.domain.moderation.moderation_action import ModerationAction
        action_required = action != ModerationAction.IGNORE

        # 3. Build decision
        decision = ModerationDecision(
            message_id=message_id,
            labels=rule_evaluation.labels,
            primary_label=rule_evaluation.primary_label,
            risk_score=rule_evaluation.risk_score,
            confidence=rule_evaluation.confidence,
            severity=rule_evaluation.severity,
            decision_action=action,
            action_required=action_required,
            dry_run=current_policy.dry_run,
            reason=reason,
            rule_evaluation=rule_evaluation,
            policy_id=current_policy.policy_id,
            policy_version=current_policy.version,
            created_at=datetime.now(),
            metadata={},
        )

        logger.info(
            f"Decision Engine finished for {message_id}. "
            f"Action: {decision.decision_action}, Required: {decision.action_required}"
        )

        return decision

from __future__ import annotations

from src.domain.decision.moderation_action_plan import ModerationActionPlan
from src.domain.moderation.moderation_action import ModerationAction
from src.infrastructure.logging.logger import get_logger
from src.modules.decision.decision_policy import DecisionPolicy

logger = get_logger(__name__)


class ActionPlanBuilder:
    _COMPOSITE_ACTIONS = {
        ModerationAction.DELETE_WARN,
    }

    def build(self, primary_action: ModerationAction, policy: DecisionPolicy) -> ModerationActionPlan:
        configured_actions = policy.action_bundles.get(primary_action)
        actions = self._normalize_actions(primary_action, configured_actions)
        required_actions = [action for action in actions if action != primary_action]

        if configured_actions:
            reason = f"Action bundle: {primary_action.value} -> {', '.join(action.value for action in actions)}"
        else:
            reason = f"Single action: {primary_action.value}"

        logger.debug(
            "Decision action plan built primary_action=%s actions=%s required_actions=%s reason=%s",
            primary_action,
            [action.value for action in actions],
            [action.value for action in required_actions],
            reason,
        )

        return ModerationActionPlan(
            primary_action=primary_action,
            actions=actions,
            required_actions=required_actions,
            reason=reason,
        )

    def _normalize_actions(
        self,
        primary_action: ModerationAction,
        configured_actions: list[ModerationAction] | None,
    ) -> list[ModerationAction]:
        actions = configured_actions[:] if configured_actions else [primary_action]

        if primary_action not in actions and primary_action not in self._COMPOSITE_ACTIONS:
            actions.append(primary_action)

        return self._deduplicate(actions)

    def _deduplicate(self, actions: list[ModerationAction]) -> list[ModerationAction]:
        unique_actions: list[ModerationAction] = []
        seen_actions: set[ModerationAction] = set()

        for action in actions:
            if action in seen_actions:
                continue

            unique_actions.append(action)
            seen_actions.add(action)

        return unique_actions

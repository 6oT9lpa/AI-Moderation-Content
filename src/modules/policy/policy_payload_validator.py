from __future__ import annotations

from typing import Any

from src.domain.policy.policy_type import PolicyType
from src.modules.action.action_policy_config_loader import ActionPolicyConfigLoader
from src.modules.decision.decision_policy_config_loader import DecisionPolicyConfigLoader
from src.modules.preprocessing.rules.preprocessing_rule_config_loader import PreprocessingRuleConfigLoader
from src.modules.rules.moderation_rule_policy_config_loader import ModerationRulePolicyConfigLoader


class PolicyPayloadValidator:
    def validate(self, policy_type: PolicyType, payload: dict[str, Any]) -> object:
        normalized_payload = self._extract_payload(policy_type, payload)

        if policy_type == PolicyType.PREPROCESSING:
            return PreprocessingRuleConfigLoader().load_from_payload(normalized_payload)

        if policy_type == PolicyType.MODERATION_RULE:
            return ModerationRulePolicyConfigLoader.load_from_payload(normalized_payload)

        if policy_type == PolicyType.DECISION:
            return DecisionPolicyConfigLoader.load_from_payload(normalized_payload)

        if policy_type == PolicyType.ACTION:
            return ActionPolicyConfigLoader.load_from_payload(normalized_payload)

        raise ValueError(f"Unsupported policy type: {policy_type}")

    def _extract_payload(self, policy_type: PolicyType, payload: dict[str, Any]) -> dict[str, Any]:
        if policy_type == PolicyType.PREPROCESSING and isinstance(payload.get("preprocessing"), dict):
            return dict(payload["preprocessing"])

        if policy_type == PolicyType.ACTION and isinstance(payload.get("action_policy"), dict):
            return dict(payload["action_policy"])

        return dict(payload)

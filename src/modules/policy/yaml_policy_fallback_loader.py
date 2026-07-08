from __future__ import annotations

from pathlib import Path

from src.domain.policy.policy_type import PolicyType
from src.infrastructure.logging.logger import get_logger
from src.modules.action.action_policy_config_loader import ActionPolicyConfigLoader
from src.modules.decision.decision_policy_config_loader import DecisionPolicyConfigLoader
from src.modules.preprocessing.rules.preprocessing_rule_config_loader import PreprocessingRuleConfigLoader
from src.modules.rules.moderation_rule_policy_config_loader import ModerationRulePolicyConfigLoader

logger = get_logger(__name__)


class YamlPolicyFallbackLoader:
    def __init__(
        self,
        *,
        preprocessing_path: str | Path = "configs/rules/preprocessing_rules.yaml",
        moderation_rule_path: str | Path = "configs/rules/moderation_rule_policy.yaml",
        decision_path: str | Path = "configs/rules/decision_policy.yaml",
        action_path: str | Path = "configs/rules/action_policy.yaml",
    ) -> None:
        self._preprocessing_path = Path(preprocessing_path)
        self._moderation_rule_path = Path(moderation_rule_path)
        self._decision_path = Path(decision_path)
        self._action_path = Path(action_path)

    def load(self, policy_type: PolicyType) -> object:
        logger.info("Loading YAML fallback policy policy_type=%s", policy_type.value)

        if policy_type == PolicyType.PREPROCESSING:
            return PreprocessingRuleConfigLoader().load(self._preprocessing_path)

        if policy_type == PolicyType.MODERATION_RULE:
            return ModerationRulePolicyConfigLoader.load(self._moderation_rule_path)

        if policy_type == PolicyType.DECISION:
            return DecisionPolicyConfigLoader.load(self._decision_path)

        if policy_type == PolicyType.ACTION:
            return ActionPolicyConfigLoader.load(self._action_path)

        raise ValueError(f"Unsupported YAML fallback policy type: {policy_type}")

import yaml
from pathlib import Path
from typing import Optional

from src.infrastructure.logging.logger import get_logger
from src.modules.rules.moderation_rule_policy import ModerationRulePolicy

logger = get_logger(__name__)


class ModerationRulePolicyConfigLoader:
    DEFAULT_CONFIG_PATH = Path("configs/rules/moderation_rule_policy.yaml")

    @classmethod
    def load(cls, path: Optional[Path] = None) -> ModerationRulePolicy:
        config_path = path or cls.DEFAULT_CONFIG_PATH

        logger.info(f"Loading moderation rule policy from {config_path}")

        if not config_path.exists():
            logger.error(f"Policy file not found: {config_path}")
            raise FileNotFoundError(f"Policy file not found: {config_path}")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            policy = ModerationRulePolicy(**data)
            logger.info(
                f"Successfully loaded policy '{policy.policy_id}' version {policy.version}"
            )
            return policy
        except Exception as e:
            logger.error(f"Failed to load moderation rule policy: {e}")
            raise

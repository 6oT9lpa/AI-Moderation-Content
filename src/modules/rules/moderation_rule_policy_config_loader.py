import yaml
from pathlib import Path
from typing import Optional

from src.infrastructure.logging.logger import get_logger
from src.contracts.rules.moderation_rule_policy import ModerationRulePolicy

logger = get_logger(__name__)


class ModerationRulePolicyConfigLoader:
    DEFAULT_CONFIG_PATH = Path("configs/rules/moderation_rule_policy.yaml")

    @classmethod
    def load(cls, path: Optional[Path] = None) -> ModerationRulePolicy:
        config_path = path or cls.DEFAULT_CONFIG_PATH

        logger.info("Loading moderation rule policy path=%s", config_path)

        if not config_path.exists():
            logger.error("Moderation rule policy file not found path=%s", config_path)
            raise FileNotFoundError(f"Policy file not found: {config_path}")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            policy = ModerationRulePolicy.model_validate(data)
            logger.info(
                "Successfully loaded moderation rule policy policy_id=%s version=%s",
                policy.policy_id,
                policy.version,
            )
            return policy
        except Exception as e:
            logger.error("Failed to load moderation rule policy error=%s", e, exc_info=True)
            raise

    @classmethod
    def load_from_payload(cls, payload: dict) -> ModerationRulePolicy:
        logger.info("Loading moderation rule policy from payload")
        try:
            policy = ModerationRulePolicy.model_validate(payload)
            logger.info(
                "Successfully loaded moderation rule policy from payload policy_id=%s version=%s",
                policy.policy_id,
                policy.version,
            )
            return policy
        except Exception as e:
            logger.error("Failed to load moderation rule policy payload error=%s", e, exc_info=True)
            raise

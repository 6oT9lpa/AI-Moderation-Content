import yaml
from pathlib import Path
from typing import Optional

from src.infrastructure.logging.logger import get_logger
from src.modules.decision.decision_policy import DecisionPolicy

logger = get_logger(__name__)


class DecisionPolicyConfigLoader:
    DEFAULT_CONFIG_PATH = Path("configs/rules/decision_policy.yaml")

    @classmethod
    def load(cls, path: Optional[Path] = None) -> DecisionPolicy:
        config_path = path or cls.DEFAULT_CONFIG_PATH

        logger.info("Loading decision policy path=%s", config_path)

        if not config_path.exists():
            logger.error("Decision policy file not found path=%s", config_path)
            raise FileNotFoundError(f"Decision policy file not found: {config_path}")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            policy = DecisionPolicy.model_validate(data)
            logger.info(
                "Successfully loaded decision policy policy_id=%s version=%s",
                policy.policy_id,
                policy.version,
            )
            return policy
        except Exception as e:
            logger.error("Failed to load decision policy error=%s", e, exc_info=True)
            raise

    @classmethod
    def load_from_payload(cls, payload: dict) -> DecisionPolicy:
        logger.info("Loading decision policy from payload")
        try:
            policy = DecisionPolicy.model_validate(payload)
            logger.info(
                "Successfully loaded decision policy from payload policy_id=%s version=%s",
                policy.policy_id,
                policy.version,
            )
            return policy
        except Exception as e:
            logger.error("Failed to load decision policy payload error=%s", e, exc_info=True)
            raise

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

        logger.info(f"Loading decision policy from {config_path}")

        if not config_path.exists():
            logger.error(f"Decision policy file not found: {config_path}")
            raise FileNotFoundError(f"Decision policy file not found: {config_path}")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            policy = DecisionPolicy(**data)
            logger.info(
                f"Successfully loaded decision policy '{policy.policy_id}' version {policy.version}"
            )
            return policy
        except Exception as e:
            logger.error(f"Failed to load decision policy: {e}")
            raise

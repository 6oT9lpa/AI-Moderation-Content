from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from src.domain.action.action_policy import ActionPolicy
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ActionPolicyConfigLoader:
    DEFAULT_CONFIG_PATH = Path("configs/rules/action_policy.yaml")

    @classmethod
    def load(cls, path: Path | None = None) -> ActionPolicy:
        config_path = path or cls.DEFAULT_CONFIG_PATH
        logger.info("Loading action policy path=%s", config_path)

        if not config_path.exists():
            logger.error("Action policy file not found path=%s", config_path)
            raise FileNotFoundError(f"Action policy file not found: {config_path}")

        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            payload = cls._extract_action_policy(data)
            policy = ActionPolicy.model_validate(payload)
            logger.info(
                "Successfully loaded action policy policy_id=%s version=%s dry_run=%s",
                policy.policy_id,
                policy.version,
                policy.dry_run,
            )
            return policy
        except Exception as exc:
            logger.error("Failed to load action policy error=%s", exc, exc_info=True)
            raise

    @classmethod
    def load_from_payload(cls, payload: Mapping[str, Any]) -> ActionPolicy:
        logger.info("Loading action policy from payload")
        try:
            policy = ActionPolicy.model_validate(cls._extract_action_policy(payload))
            logger.info(
                "Successfully loaded action policy from payload policy_id=%s version=%s dry_run=%s",
                policy.policy_id,
                policy.version,
                policy.dry_run,
            )
            return policy
        except Exception as exc:
            logger.error("Failed to load action policy payload error=%s", exc, exc_info=True)
            raise

    @classmethod
    def _extract_action_policy(cls, data: Mapping[str, Any]) -> Mapping[str, Any]:
        action_policy = data.get("action_policy")

        if isinstance(action_policy, Mapping):
            return action_policy

        return data

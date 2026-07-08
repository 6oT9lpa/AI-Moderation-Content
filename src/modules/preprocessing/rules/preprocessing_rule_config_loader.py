from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.infrastructure.logging import get_logger
from src.modules.preprocessing.rules.preprocessing_moderation_policy_adapter import (
    PreprocessingModerationPolicyAdapter,
)
from src.modules.preprocessing.rules.preprocessing_rule_settings import PreprocessingRuleSettings
from src.contracts.rules.moderation_rule_policy import ModerationRulePolicy
from src.modules.rules.moderation_rule_policy_config_loader import ModerationRulePolicyConfigLoader

logger = get_logger(__name__)


class PreprocessingRuleConfigLoader:
    def __init__(
        self,
        *,
        moderation_policy: ModerationRulePolicy | None = None,
        moderation_policy_path: str | Path = "configs/rules/moderation_rule_policy.yaml",
        policy_adapter: PreprocessingModerationPolicyAdapter | None = None,
    ) -> None:
        self._moderation_policy = moderation_policy
        self._moderation_policy_path = Path(moderation_policy_path)
        self._policy_adapter = policy_adapter or PreprocessingModerationPolicyAdapter()

    def load(self, path: str | Path) -> PreprocessingRuleSettings:
        config_path = Path(path)
        logger.info("Preprocessing rule config loading path=%s", config_path)

        if not config_path.exists():
            logger.warning("Preprocessing rule config missing path=%s using_defaults=true", config_path)
            return self._policy_adapter.adapt(PreprocessingRuleSettings(), self._resolve_moderation_policy())

        data = self._load_yaml_data(config_path)
        rule_data = self._extract_rule_data(data)
        settings = PreprocessingRuleSettings.from_mapping(rule_data)
        adapted_settings = self._policy_adapter.adapt(settings, self._resolve_moderation_policy())
        logger.info("Preprocessing rule config loaded path=%s settings=%s", config_path, adapted_settings)
        return adapted_settings

    def load_from_payload(self, payload: Mapping[str, Any]) -> PreprocessingRuleSettings:
        logger.info("Preprocessing rule config loading from payload")
        rule_data = self._extract_rule_data(payload)
        settings = PreprocessingRuleSettings.from_mapping(rule_data)
        adapted_settings = self._policy_adapter.adapt(settings, self._resolve_moderation_policy())
        logger.info("Preprocessing rule config payload loaded settings=%s", adapted_settings)
        return adapted_settings

    def _resolve_moderation_policy(self) -> ModerationRulePolicy:
        if self._moderation_policy is not None:
            return self._moderation_policy

        self._moderation_policy = ModerationRulePolicyConfigLoader.load(self._moderation_policy_path)
        return self._moderation_policy

    def _load_yaml_data(self, config_path: Path) -> Mapping[str, Any]:
        try:
            import yaml

            return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except ModuleNotFoundError:
            logger.warning("PyYAML is not installed, using simple preprocessing YAML parser")
            return self._load_simple_yaml(config_path)

    def _load_simple_yaml(self, config_path: Path) -> Mapping[str, Any]:
        root: dict[str, Any] = {}
        stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

        for raw_line in config_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.split("#", 1)[0].rstrip()

            if not line.strip():
                continue

            if ":" not in line:
                continue

            indent = len(raw_line) - len(raw_line.lstrip(" "))
            key, raw_value = line.strip().split(":", 1)

            while stack and indent <= stack[-1][0]:
                stack.pop()

            parent = stack[-1][1]

            if not raw_value.strip():
                section: dict[str, Any] = {}
                parent[key.strip()] = section
                stack.append((indent, section))
                continue

            parent[key.strip()] = self._parse_scalar(raw_value.strip())

        return root

    def _parse_scalar(self, value: str) -> object:
        if value.startswith("[") and value.endswith("]"):
            return [
                self._parse_scalar(item.strip())
                for item in value[1:-1].split(",")
                if item.strip()
            ]

        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            return value[1:-1]

        if value.lower() in {"null", "none"}:
            return None

        if value.lower() in {"true", "false"}:
            return value.lower() == "true"

        try:
            return int(value)
        except ValueError:
            pass

        try:
            return float(value)
        except ValueError:
            return value

    def _extract_rule_data(self, data: Mapping[str, Any]) -> Mapping[str, Any]:
        preprocessing = data.get("preprocessing")

        if isinstance(preprocessing, Mapping):
            return preprocessing

        return data

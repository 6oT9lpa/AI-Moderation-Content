from __future__ import annotations

from pathlib import Path

import yaml

from src.infrastructure.logging import get_logger
from src.modules.media.media_rule_settings import MediaRuleSettings

logger = get_logger(__name__)


class MediaRuleConfigLoader:
    DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs/rules/media_rules.yaml"

    @classmethod
    def load(cls, path: str | Path | None = None) -> MediaRuleSettings:
        config_path = Path(path) if path is not None else cls.DEFAULT_CONFIG_PATH
        logger.info("Loading media rule settings path=%s", config_path)
        with config_path.open("r", encoding="utf-8") as config_file:
            settings = MediaRuleSettings.model_validate(yaml.safe_load(config_file) or {})
        logger.info("Media rule settings loaded version=%s", settings.version)
        return settings

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from src.application.ports.media.media_policy_defaults_provider import MediaPolicyDefaultsProvider
from src.domain.media.media_rule_policy import MediaRulePolicy, OcrRulePolicy, YoloRulePolicy
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class DuplicateKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: DuplicateKeySafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key: {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


DuplicateKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


class YamlMediaPolicyDefaultsProvider(MediaPolicyDefaultsProvider):
    def __init__(self, *, ocr_path: Path, yolo_path: Path) -> None:
        self._policy = MediaRulePolicy(
            ocr=OcrRulePolicy.model_validate(self._load(ocr_path)),
            yolo=YoloRulePolicy.model_validate(self._load(yolo_path)),
        )
        self._log_loaded(ocr_path, self._policy.ocr.version)
        self._log_loaded(yolo_path, self._policy.yolo.version)

    def get_defaults(self) -> MediaRulePolicy:
        return self._policy

    @staticmethod
    def _load(path: Path) -> object:
        payload = path.read_bytes()
        parsed = yaml.load(payload.decode("utf-8"), Loader=DuplicateKeySafeLoader)
        if not isinstance(parsed, dict):
            raise ValueError(f"media policy must be a mapping: {path.name}")
        return parsed

    @staticmethod
    def _log_loaded(path: Path, version: str) -> None:
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        logger.info(
            "Media policy defaults loaded file=%s version=%s checksum=%s",
            path.name,
            version,
            checksum,
        )

from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
from typing import Any

import yaml

from src.domain.media.known_scam_image_hash import KnownScamImageHash
from src.domain.moderation.scam_subtype import ScamSubtype
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class KnownScamImageHashConfigLoader:
    DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs/rules/known_scam_image_hashes.yaml"

    @classmethod
    def load(cls, path: str | Path | None = None) -> tuple[KnownScamImageHash, ...]:
        config_path = Path(path) if path is not None else cls.DEFAULT_CONFIG_PATH
        logger.info("Loading known scam image hashes path=%s", config_path)
        with config_path.open("r", encoding="utf-8") as config_file:
            data = yaml.safe_load(config_file) or {}
        if not isinstance(data, Mapping):
            logger.error("Known scam image hash config is invalid path=%s reason=top_level_mapping_required", config_path)
            raise ValueError("known scam image hash config must be a mapping")
        version = data.get("version")
        if not isinstance(version, str) or not version.strip():
            logger.error("Known scam image hash config is invalid path=%s reason=version_required", config_path)
            raise ValueError("known scam image hash config version is required")
        source_records = data.get("records", [])
        if not isinstance(source_records, list):
            logger.error("Known scam image hash config is invalid path=%s reason=records_list_required", config_path)
            raise ValueError("known scam image hash config records must be a list")
        records: list[KnownScamImageHash] = []
        for index, source_record in enumerate(source_records):
            try:
                records.append(cls._build_record(source_record))
            except ValueError as exc:
                logger.error(
                    "Known scam image hash config is invalid path=%s record_index=%s reason=%s",
                    config_path,
                    index,
                    exc,
                )
                raise
        immutable_records = tuple(records)
        record_ids = [record.record_id for record in immutable_records]
        if len(record_ids) != len(set(record_ids)):
            logger.error("Known scam image hash config is invalid path=%s reason=duplicate_record_id", config_path)
            raise ValueError("known scam image hash config record_id values must be unique")
        if not immutable_records:
            logger.warning("Known scam image hash registry is empty path=%s", config_path)
        logger.info("Known scam image hashes loaded path=%s records=%s", config_path, len(immutable_records))
        return immutable_records

    @staticmethod
    def _build_record(data: Mapping[str, Any]) -> KnownScamImageHash:
        if not isinstance(data, Mapping):
            raise ValueError("known scam image hash record must be a mapping")
        record_id = data.get("record_id")
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("known scam image hash record_id is required")
        subtype = data.get("scam_subtype")
        return KnownScamImageHash(
            record_id=record_id,
            phash=data.get("phash"),
            dhash=data.get("dhash"),
            ahash=data.get("ahash"),
            scam_subtype=ScamSubtype(subtype) if subtype else None,
        )

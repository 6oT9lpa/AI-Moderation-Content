from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_label_priority import resolve_primary_label
from src.training.rubert.rubert_training_config import RuBertTrainingConfig


class ModerationDatasetSchema:
    def __init__(self, labels: Iterable[ModerationLabel]) -> None:
        self._labels = tuple(labels)
        self._label_index = {label: index for index, label in enumerate(self._labels)}

        if len(self._label_index) != len(self._labels):
            raise ValueError("Dataset labels must be unique")

    @classmethod
    def from_training_config(cls, path: str | Path) -> "ModerationDatasetSchema":
        config = RuBertTrainingConfig.load(path)
        return cls(config.label_schema.labels)

    @property
    def labels(self) -> tuple[ModerationLabel, ...]:
        return self._labels

    @property
    def label_names(self) -> tuple[str, ...]:
        return tuple(label.value for label in self._labels)

    def normalize_row(
        self,
        row: Mapping[str, Any],
        *,
        added_labels: Iterable[ModerationLabel] = (),
        minimum_severity: int = 0,
        record_id: int | str | None = None,
    ) -> dict[str, Any]:
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Dataset row must contain non-empty text")

        selected = self._read_labels(row)
        selected.update(added_labels)
        selected = self._normalize_safe(selected)
        ordered = tuple(label for label in self._labels if label in selected)
        severity = max(int(row.get("severity", 0)), int(minimum_severity))

        if ordered == (ModerationLabel.SAFE,):
            severity = 0

        resolved_id = row.get("id") if record_id is None else record_id
        if resolved_id is None:
            raise ValueError("Dataset row must contain id")

        return {
            "text": text.strip(),
            "labels": [1.0 if label in selected else 0.0 for label in self._labels],
            "label_names": [label.value for label in ordered],
            "primary_label": resolve_primary_label(ordered).value,
            "severity": severity,
            "id": resolved_id,
        }

    def build_row(
        self,
        *,
        text: str,
        labels: Iterable[ModerationLabel],
        severity: int,
        record_id: int | str,
    ) -> dict[str, Any]:
        return self.normalize_row(
            {
                "text": text,
                "label_names": [label.value for label in labels],
                "severity": severity,
                "id": record_id,
            }
        )

    def validate_row(self, row: Mapping[str, Any]) -> None:
        normalized = self.normalize_row(row)
        vector = row.get("labels")

        if not isinstance(vector, list) or len(vector) != len(self._labels):
            raise ValueError(f"Expected {len(self._labels)} label values")

        normalized_vector = [float(value) for value in vector]
        if normalized_vector != normalized["labels"]:
            raise ValueError("labels vector and label_names disagree")

        if row.get("primary_label") != normalized["primary_label"]:
            raise ValueError("primary_label does not match label priority")

        if int(row.get("severity", 0)) != normalized["severity"]:
            raise ValueError("severity is not normalized")

    def labels_to_mask(self, labels: Iterable[ModerationLabel]) -> int:
        selected = self._normalize_safe(set(labels))
        mask = 0
        for label in selected:
            mask |= 1 << self._label_index[label]
        return mask

    def mask_to_labels(self, mask: int) -> tuple[ModerationLabel, ...]:
        selected = {
            label
            for index, label in enumerate(self._labels)
            if mask & (1 << index)
        }
        selected = self._normalize_safe(selected)
        return tuple(label for label in self._labels if label in selected)

    def row_to_mask(self, row: Mapping[str, Any]) -> int:
        return self.labels_to_mask(self._read_labels(row))

    def _read_labels(self, row: Mapping[str, Any]) -> set[ModerationLabel]:
        raw_names = row.get("label_names")
        if not isinstance(raw_names, list):
            raise ValueError("Dataset row must contain label_names")

        selected: set[ModerationLabel] = set()
        for name in raw_names:
            label = ModerationLabel(str(name))
            if label not in self._label_index:
                raise ValueError(f"Label {label.value} is not in the training schema")
            selected.add(label)

        if not selected:
            selected.add(ModerationLabel.SAFE)
        return selected

    @staticmethod
    def _normalize_safe(labels: set[ModerationLabel]) -> set[ModerationLabel]:
        normalized = set(labels)
        if len(normalized) > 1:
            normalized.discard(ModerationLabel.SAFE)
        if not normalized:
            normalized.add(ModerationLabel.SAFE)
        return normalized

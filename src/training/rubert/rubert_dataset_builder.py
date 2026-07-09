from __future__ import annotations

from typing import Any

from src.domain.dto.dataset.training_example import TrainingExample
from src.training.datasets.moderation_label_priority import resolve_primary_label
from src.training.rubert.rubert_label_schema import RuBertLabelSchema


class RuBertDatasetBuilder:
    def __init__(self, label_schema: RuBertLabelSchema | None = None) -> None:
        self._label_schema = label_schema or RuBertLabelSchema()

    def build_rows(self, examples: list[TrainingExample]) -> list[dict[str, Any]]:
        return [
            {
                "event_id": example.event_id,
                "message_id": example.message_id,
                "text": example.model_text,
                "labels": self._label_schema.encode_labels(example.labels),
                "label_names": [label.value for label in example.labels],
                "primary_label": resolve_primary_label(example.labels or [example.primary_label]).value,
                "severity": example.severity,
                "source": example.source.value,
                "risk_score": example.risk_score,
                "decision_action": example.decision_action.value,
                "feedback_type": example.feedback_type.value if example.feedback_type else None,
                "policy_version": example.policy_version,
                "features": example.features,
                "rule_matches": example.rule_matches,
                "created_at": example.created_at.isoformat(),
            }
            for example in examples
        ]

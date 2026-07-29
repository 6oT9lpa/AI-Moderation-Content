from pathlib import Path

import pytest

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema


CONFIG_PATH = Path("configs/training/rubert_tiny2.yaml")


def test_schema_adds_labels_and_keeps_safe_exclusive() -> None:
    schema = ModerationDatasetSchema.from_training_config(CONFIG_PATH)

    row = schema.normalize_row(
        {
            "text": "example",
            "label_names": ["SAFE"],
            "severity": 1,
            "id": 1,
        },
        added_labels=(ModerationLabel.HATE, ModerationLabel.TOXIC),
        minimum_severity=4,
    )

    assert row["label_names"] == ["TOXIC", "HATE"]
    assert row["primary_label"] == "HATE"
    assert row["severity"] == 4
    assert row["labels"][0] == 0.0


def test_schema_normalizes_safe_severity_to_zero() -> None:
    schema = ModerationDatasetSchema.from_training_config(CONFIG_PATH)

    row = schema.normalize_row(
        {
            "text": "benign",
            "label_names": ["SAFE"],
            "severity": 3,
            "id": "safe-1",
        }
    )

    assert row["severity"] == 0
    assert row["primary_label"] == "SAFE"


def test_schema_rejects_labels_outside_training_config() -> None:
    schema = ModerationDatasetSchema.from_training_config(CONFIG_PATH)

    with pytest.raises(ValueError, match="not in the training schema"):
        schema.normalize_row(
            {
                "text": "flood",
                "label_names": ["FLOOD"],
                "severity": 2,
                "id": 1,
            }
        )

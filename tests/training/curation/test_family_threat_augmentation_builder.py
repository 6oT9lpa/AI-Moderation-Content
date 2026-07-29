import json
from pathlib import Path

from src.training.curation.dataset_split_assigner import DatasetSplitAssigner
from src.training.curation.family_threat_augmentation_builder import (
    FamilyThreatAugmentationBuilder,
)
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema
from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher


TRAINING_CONFIG = Path("configs/training/rubert_tiny2.yaml")
CURATION_CONFIG = Path("configs/training/sensitive_topic_curation.yaml")


def test_family_threat_builder_never_generates_hate(tmp_path: Path) -> None:
    builder = FamilyThreatAugmentationBuilder(
        schema=ModerationDatasetSchema.from_training_config(TRAINING_CONFIG),
        matcher=SensitiveTopicMatcher.from_yaml(CURATION_CONFIG),
        split_assigner=DatasetSplitAssigner(
            validation_fraction=0.15,
            seed="test-family-threats",
        ),
    )

    report = builder.build(output_dir=tmp_path)

    rows = []
    for split in ("train", "validation"):
        rows.extend(
            json.loads(line)
            for line in (tmp_path / f"{split}.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    assert len(rows) == 640
    assert report["counts"]["label_THREAT"] == 640
    assert report["counts"]["label_TOXIC"] == 640
    assert all("HATE" not in row["label_names"] for row in rows)
    assert all({"THREAT", "TOXIC"}.issubset(row["label_names"]) for row in rows)

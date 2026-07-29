import json
from pathlib import Path

from src.training.curation.dataset_split_assigner import DatasetSplitAssigner
from src.training.curation.invite_augmentation_builder import InviteAugmentationBuilder
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema


CONFIG_PATH = Path("configs/training/rubert_tiny2.yaml")


def test_invite_builder_produces_requested_unique_rows(tmp_path: Path) -> None:
    builder = InviteAugmentationBuilder(
        schema=ModerationDatasetSchema.from_training_config(CONFIG_PATH),
        split_assigner=DatasetSplitAssigner(
            validation_fraction=0.2,
            seed="test-invites",
        ),
        target_rows=200,
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
    assert len(rows) == 200
    assert len({" ".join(row["text"].casefold().split()) for row in rows}) == 200
    assert sum(report["counts"].values()) == 200
    assert all(row["label_names"] == ["INVITE", "URL"] for row in rows)
    assert all("<INVITE>" in row["text"] for row in rows)

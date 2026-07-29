import json
from pathlib import Path

from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema
from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher
from src.training.curation.sensitive_topic_relabeler import SensitiveTopicRelabeler


def test_relabeler_adds_family_threat_and_writes_change(tmp_path: Path) -> None:
    schema = ModerationDatasetSchema.from_training_config("configs/training/rubert_tiny2.yaml")
    matcher = SensitiveTopicMatcher.from_yaml("configs/training/sensitive_topic_curation.yaml")
    input_path = tmp_path / "input.jsonl"
    output_path = tmp_path / "output.jsonl"
    changes_path = tmp_path / "changes.jsonl"
    review_path = tmp_path / "review.jsonl"
    input_path.write_text(
        json.dumps(
            schema.build_row(
                text="Я найду твою семью и убью",
                labels=[],
                severity=0,
                record_id=1,
            ),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    report = SensitiveTopicRelabeler(schema=schema, matcher=matcher).relabel_file(
        input_path=input_path,
        output_path=output_path,
        changes_path=changes_path,
        review_path=review_path,
    )

    row = json.loads(output_path.read_text(encoding="utf-8"))
    assert set(row["label_names"]) >= {"THREAT", "TOXIC"}
    assert report["changed_rows"] == 1
    assert changes_path.read_text(encoding="utf-8").strip()


def test_relabeler_does_not_change_neutral_family_text(tmp_path: Path) -> None:
    schema = ModerationDatasetSchema.from_training_config("configs/training/rubert_tiny2.yaml")
    matcher = SensitiveTopicMatcher.from_yaml("configs/training/sensitive_topic_curation.yaml")
    input_path = tmp_path / "input.jsonl"
    output_path = tmp_path / "output.jsonl"
    input_path.write_text(
        json.dumps(
            schema.build_row(
                text="Моя семья приехала в гости",
                labels=[],
                severity=0,
                record_id=1,
            ),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    report = SensitiveTopicRelabeler(schema=schema, matcher=matcher).relabel_file(
        input_path=input_path,
        output_path=output_path,
        changes_path=tmp_path / "changes.jsonl",
        review_path=tmp_path / "review.jsonl",
    )

    row = json.loads(output_path.read_text(encoding="utf-8"))
    assert row["label_names"] == ["SAFE"]
    assert report["changed_rows"] == 0

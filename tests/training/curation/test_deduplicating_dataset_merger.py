import json
from pathlib import Path

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.deduplicating_dataset_merger import DeduplicatingDatasetMerger
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema


def test_merger_unions_duplicate_labels_and_gives_validation_priority(tmp_path: Path) -> None:
    schema = ModerationDatasetSchema.from_training_config("configs/training/rubert_tiny2.yaml")
    base = tmp_path / "base"
    external = tmp_path / "external"
    base.mkdir()
    external.mkdir()

    _write(
        base / "train.jsonl",
        [
            schema.build_row(
                text="same text",
                labels=(ModerationLabel.TOXIC,),
                severity=2,
                record_id=1,
            ),
            schema.build_row(
                text="train only",
                labels=(ModerationLabel.SAFE,),
                severity=0,
                record_id=2,
            ),
        ],
    )
    _write(
        base / "validation.jsonl",
        [
            schema.build_row(
                text="validation only",
                labels=(ModerationLabel.SAFE,),
                severity=0,
                record_id=1,
            )
        ],
    )
    _write(external / "train.jsonl", [])
    _write(
        external / "validation.jsonl",
        [
            schema.build_row(
                text=" SAME   TEXT ",
                labels=(ModerationLabel.HATE,),
                severity=4,
                record_id="external-1",
            )
        ],
    )

    report = DeduplicatingDatasetMerger(schema=schema).merge_into(
        sources=(
            ("base", base / "train.jsonl", base / "validation.jsonl"),
            ("external", external / "train.jsonl", external / "validation.jsonl"),
        ),
        target_dir=base,
    )

    train = _read(base / "train.jsonl")
    validation = _read(base / "validation.jsonl")
    merged = next(row for row in validation if row["text"] == "same text")
    assert set(merged["label_names"]) == {"TOXIC", "HATE"}
    assert all(row["text"] != "same text" for row in train)
    assert report["database"]["texts_seen_in_both_splits"] == 1
    assert report["result"]["cross_split_overlap"] == 0
    assert Path(report["backup_dir"]).is_dir()
    assert not list(base.glob("*.tmp"))
    assert not list(base.glob(".sensitive-topic-merge-*.sqlite3"))


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

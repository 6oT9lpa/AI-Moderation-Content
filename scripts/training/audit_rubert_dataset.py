from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.datasets.hard_eval_pack import build_hard_eval_pack
from src.training.datasets.moderation_export_relabeler import ModerationExportRelabeler
from src.training.datasets.moderation_label_priority import resolve_primary_label
from src.training.datasets.unseen_hard_eval_pack import build_unseen_hard_eval_pack


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and optionally normalize ruBERT JSONL dataset splits.")
    parser.add_argument("--dataset-dir", type=Path, default=Path("data/exports/rubert_moderation_v1"))
    parser.add_argument("--apply", action="store_true", help="Write normalized labels, severity and metadata.")
    args = parser.parse_args()

    relabeler = ModerationExportRelabeler()
    split_rows: dict[str, list[dict]] = {}
    all_rows: list[tuple[str, dict]] = []
    rule_label_gaps = Counter()
    invalid_primary = []

    for split_name in ("train", "validation", "test"):
        path = args.dataset_dir / f"{split_name}.jsonl"
        rows = _read_rows(path)
        updated_rows = []
        for row in rows:
            labels = relabeler._extract_label_names(row)
            expected_primary = resolve_primary_label(labels).value
            if row.get("primary_label") != expected_primary:
                invalid_primary.append({"split": split_name, "message_id": row.get("message_id")})

            detected = relabeler._analyze_text(str(row.get("text") or row.get("model_text") or ""))
            for label in detected - labels:
                rule_label_gaps[label.value] += 1

            updated_rows.append(relabeler.relabel_row(row) if args.apply else row)
            all_rows.append((split_name, row))

        if args.apply:
            _write_rows(path, updated_rows)
        split_rows[split_name] = updated_rows

    locations: dict[str, set[str]] = defaultdict(set)
    labels_by_text: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for split_name, row in all_rows:
        text = str(row.get("text") or row.get("model_text") or "").strip().casefold()
        labels = tuple(sorted(relabeler._extract_label_names(row), key=lambda label: label.value))
        locations[text].add(split_name)
        labels_by_text[text].add(tuple(label.value for label in labels))

    hard_texts = {row["text"].casefold() for row in build_hard_eval_pack()}
    unseen_texts = {row["text"].casefold() for row in build_unseen_hard_eval_pack()}
    train_texts = {str(row.get("text") or row.get("model_text") or "").strip().casefold() for row in split_rows["train"]}

    report = {
        "dataset_dir": str(args.dataset_dir),
        "applied": args.apply,
        "split_counts": {name: len(rows) for name, rows in split_rows.items()},
        "cross_split_duplicates": sum(1 for splits in locations.values() if len(splits) > 1),
        "conflicting_labels_for_same_text": sum(1 for labels in labels_by_text.values() if len(labels) > 1),
        "invalid_primary_labels": len(invalid_primary),
        "rule_label_gaps": dict(sorted(rule_label_gaps.items())),
        "known_hard_pack_train_leaks": len(hard_texts & train_texts),
        "unseen_hard_pack_train_leaks": len(unseen_texts & train_texts),
        "label_counts": dict(
            Counter(
                row.get("primary_label", "UNKNOWN")
                for rows in split_rows.values()
                for row in rows
            )
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_rows(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()

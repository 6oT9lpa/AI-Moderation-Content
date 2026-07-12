from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_export_relabeler import ModerationExportRelabeler
from src.training.datasets.moderation_label_priority import resolve_primary_label
from src.training.datasets.training_text_sanitizer import TrainingTextSanitizer
from src.training.rubert.rubert_label_schema import RuBertLabelSchema


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and deterministically repair a ruBERT moderation export.")
    parser.add_argument("--dataset-dir", default="data/exports/rubert_moderation_v2")
    parser.add_argument("--apply", action="store_true", help="Apply deterministic label additions and primary-label repairs.")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    schema = RuBertLabelSchema()
    sanitizer = TrainingTextSanitizer()
    relabeler = ModerationExportRelabeler(schema)
    seen: dict[str, str] = {}
    report: dict[str, object] = {"rows": 0, "labels": Counter(), "source_counts": Counter(), "duplicates_across_splits": 0, "duplicates_removed": 0, "invalid_rows": 0, "repaired_rows": 0, "repairs_by_split": Counter()}

    for split in ("train", "validation", "test"):
        path = dataset_dir / f"{split}.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        retained_rows: list[dict] = []
        changed = False
        for row in rows:
            report["rows"] += 1
            text = str(row.get("text") or "")
            labels = [name for name in row.get("label_names", []) if name in ModerationLabel.__members__]
            if not text or not labels:
                report["invalid_rows"] += 1
                continue
            normalized = sanitizer.sanitize(text)
            if normalized in seen and seen[normalized] != split:
                report["duplicates_across_splits"] += 1
                if args.apply:
                    report["duplicates_removed"] += 1
                    changed = True
                    continue
            else:
                seen[normalized] = split
            report["labels"].update(labels)
            report["source_counts"].update([str(row.get("source") or "unknown")])

            relabeled = relabeler.relabel_row({"model_text": text, "labels": labels, "primary_label": row.get("primary_label"), "severity": row.get("severity", 0)})
            new_labels = [name for name in relabeled.get("labels", []) if name in schema.label2id]
            new_primary = str(relabeled.get("primary_label") or resolve_primary_label([ModerationLabel(name) for name in labels]).value)
            if new_labels != labels or new_primary != row.get("primary_label"):
                report["repaired_rows"] += 1
                report["repairs_by_split"].update([split])
                if args.apply:
                    row["label_names"] = new_labels
                    row["labels"] = schema.encode_labels([ModerationLabel(name) for name in new_labels])
                    row["primary_label"] = new_primary
                    row["severity"] = int(relabeled.get("severity") or row.get("severity") or 0)
                    changed = True
            retained_rows.append(row)
        if args.apply and changed:
            path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in retained_rows), encoding="utf-8")

    for key in ("labels", "source_counts", "repairs_by_split"):
        report[key] = dict(report[key])
    report["apply"] = args.apply
    (dataset_dir / "audit_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.hard_eval_pack import build_hard_eval_pack
from src.training.rubert.rubert_moderation_classifier import RuBertModerationClassifier


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Evaluate trained ruBERT on the local hard moderation pack.")
    parser.add_argument("--model-dir", type=Path, default=Path("models/rubert-tiny2-moderation-trained"))
    parser.add_argument("--show-errors", action="store_true")
    args = parser.parse_args()

    classifier = RuBertModerationClassifier(model_dir=args.model_dir)
    rows = build_hard_eval_pack()
    errors: list[dict] = []
    primary_ok = 0
    label_exact_ok = 0

    for row in rows:
        result = classifier.classify(row["text"])
        expected_primary = row["primary_label"]
        expected_labels = set(row["labels"])
        predicted_labels = {label.value for label in result.labels}
        if result.primary_label.value == expected_primary:
            primary_ok += 1
        if predicted_labels == expected_labels:
            label_exact_ok += 1
        if result.primary_label.value != expected_primary or predicted_labels != expected_labels:
            errors.append(
                {
                    "text": row["text"],
                    "expected_primary": expected_primary,
                    "predicted_primary": result.primary_label.value,
                    "expected_labels": sorted(expected_labels),
                    "predicted_labels": sorted(predicted_labels),
                    "top_labels": result.top_labels,
                    "model_text": result.model_text,
                }
            )

    report = {
        "rows": len(rows),
        "primary_accuracy": round(primary_ok / len(rows), 4),
        "label_exact_accuracy": round(label_exact_ok / len(rows), 4),
        "errors": len(errors),
    }
    if args.show_errors:
        report["error_rows"] = errors

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

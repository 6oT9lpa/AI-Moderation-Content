"""Calibrate per-label ruBERT thresholds on an independent validation JSONL.

The generated ``thresholds.json`` is consumed directly by
``RuBertModerationClassifier``.  Calibration never reads a training split.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from scripts.training.train_rubert_tiny2 import _load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--batch-size", type=int, default=128)
    return parser.parse_args()


def metrics(targets: np.ndarray, predictions: np.ndarray) -> tuple[float, float, float]:
    true_positive = int(np.logical_and(targets == 1, predictions == 1).sum())
    false_positive = int(np.logical_and(targets == 0, predictions == 1).sum())
    false_negative = int(np.logical_and(targets == 1, predictions == 0).sum())
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def best_threshold(scores: np.ndarray, targets: np.ndarray) -> tuple[float, tuple[float, float, float]]:
    """Find the exact score cutoff that maximizes per-label F1."""
    order = np.argsort(scores)[::-1]
    sorted_scores = scores[order]
    sorted_targets = targets[order].astype(np.int64)
    positives = int(sorted_targets.sum())
    true_positive = np.cumsum(sorted_targets)
    false_positive = np.arange(1, len(sorted_targets) + 1) - true_positive
    false_negative = positives - true_positive
    denominator = 2 * true_positive + false_positive + false_negative
    f1 = np.divide(2 * true_positive, denominator, out=np.zeros_like(denominator, dtype=float), where=denominator != 0)
    # A threshold is only meaningful at the final occurrence of a score.
    candidates = np.r_[sorted_scores[:-1] != sorted_scores[1:], True]
    candidate_indices = np.flatnonzero(candidates)
    index = int(candidate_indices[np.argmax(f1[candidate_indices])])
    threshold = float(sorted_scores[index])
    prediction = scores >= threshold
    return threshold, metrics(targets, prediction)


def main() -> None:
    args = parse_args()
    if args.batch_size < 1:
        raise ValueError("--batch-size must be positive")
    output = args.output or args.model_dir / "thresholds.json"
    report_path = args.report or args.model_dir / "threshold_calibration_report.json"

    import torch
    from sklearn.metrics import f1_score
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    rows = _load_jsonl(args.validation)
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(args.model_dir, local_files_only=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()
    labels = [model.config.id2label[index] for index in range(model.config.num_labels)]
    targets = np.asarray([row["labels"] for row in rows], dtype=np.int8)
    if targets.shape[1] != len(labels):
        raise ValueError(f"Validation has {targets.shape[1]} labels, model has {len(labels)}")

    scores: list[np.ndarray] = []
    with torch.inference_mode():
        for start in range(0, len(rows), args.batch_size):
            texts = [row["text"] for row in rows[start : start + args.batch_size]]
            batch = tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt")
            batch = {key: value.to(device) for key, value in batch.items()}
            scores.append(torch.sigmoid(model(**batch).logits).cpu().numpy())
    probabilities = np.concatenate(scores, axis=0)

    thresholds: dict[str, float] = {}
    labels_report: dict[str, Any] = {}
    for index, label in enumerate(labels):
        baseline = metrics(targets[:, index], probabilities[:, index] >= 0.5)
        threshold, optimized = best_threshold(probabilities[:, index], targets[:, index])
        thresholds[label] = round(threshold, 6)
        labels_report[label] = {
            "support": int(targets[:, index].sum()),
            "threshold": thresholds[label],
            "at_0_5": dict(zip(("precision", "recall", "f1"), (round(value, 6) for value in baseline), strict=True)),
            "calibrated": dict(zip(("precision", "recall", "f1"), (round(value, 6) for value in optimized), strict=True)),
        }

    raw_baseline = probabilities >= 0.5
    raw_calibrated = np.column_stack([probabilities[:, i] >= thresholds[label] for i, label in enumerate(labels)])
    safe_index = labels.index("SAFE")
    harmful = np.ones(len(labels), dtype=bool)
    harmful[safe_index] = False
    # Match the production classifier: SAFE is excluded when any harmful label is selected.
    for predictions in (raw_baseline, raw_calibrated):
        predictions[:, safe_index] &= ~predictions[:, harmful].any(axis=1)
    aggregate = {
        "at_0_5": {
            "micro_f1": round(float(f1_score(targets, raw_baseline, average="micro", zero_division=0)), 6),
            "macro_f1": round(float(f1_score(targets, raw_baseline, average="macro", zero_division=0)), 6),
            "exact_match": round(float(np.all(targets == raw_baseline, axis=1).mean()), 6),
        },
        "calibrated": {
            "micro_f1": round(float(f1_score(targets, raw_calibrated, average="micro", zero_division=0)), 6),
            "macro_f1": round(float(f1_score(targets, raw_calibrated, average="macro", zero_division=0)), 6),
            "exact_match": round(float(np.all(targets == raw_calibrated, axis=1).mean()), 6),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(thresholds, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(
        json.dumps(
            {
                "model_dir": str(args.model_dir),
                "validation": str(args.validation),
                "records": len(rows),
                "labels": labels_report,
                "aggregate": aggregate,
                "production_safe_exclusion_applied": True,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote thresholds to {output}")
    print(json.dumps(aggregate, ensure_ascii=False))


if __name__ == "__main__":
    main()

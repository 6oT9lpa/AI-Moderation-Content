from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_label_priority import resolve_primary_label
from src.training.datasets.training_text_sanitizer import TrainingTextSanitizer
from src.training.rubert.rubert_training_config import RuBertTrainingConfig


def _read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _metrics(counts: dict[str, dict[str, int]], labels: list[str]) -> tuple[dict, dict]:
    per_label: dict[str, dict[str, float | int]] = {}
    total_tp = total_fp = total_fn = 0
    f1_values: list[float] = []
    evaluated_labels: list[str] = []
    for label in labels:
        item = counts[label]
        tp, fp, fn = item["tp"], item["fp"], item["fn"]
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {
            "support": tp + fn,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
        }
        total_tp += tp
        total_fp += fp
        total_fn += fn
        if tp + fn:
            f1_values.append(f1)
            evaluated_labels.append(label)

    micro_precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    micro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall) if micro_precision + micro_recall else 0.0
    return {
        "micro_f1": round(micro_f1, 6),
        "macro_f1": round(sum(f1_values) / len(f1_values), 6),
        "evaluated_labels": evaluated_labels,
    }, per_label


def main() -> None:
    parser = argparse.ArgumentParser(description="Batched evaluation of a ruBERT checkpoint on the 50k hard-gold pack.")
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=Path("data/eval/rubert_hard_gold_v1/hard_gold.jsonl"))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--threshold", type=float, default=0.5, help="Uniform comparison threshold for both checkpoints.")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if not 0 <= args.threshold <= 1:
        raise ValueError("--threshold must be between 0 and 1")
    if args.batch_size < 1:
        raise ValueError("--batch-size must be positive")

    rows = _read_rows(args.dataset)
    config = RuBertTrainingConfig.load()
    sanitizer = TrainingTextSanitizer()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(args.model_dir, local_files_only=True, use_safetensors=True)
    model.to(device)
    model.eval()
    label_order = [model.config.id2label[index] for index in range(model.config.num_labels)]
    label_names = [label.value for label in ModerationLabel if label.value in label_order]

    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    exact = primary_ok = 0
    started = perf_counter()
    for offset in range(0, len(rows), args.batch_size):
        batch_rows = rows[offset : offset + args.batch_size]
        texts = [sanitizer.sanitize(row["text"]) for row in batch_rows]
        encoded = tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=config.model.max_length).to(device)
        with torch.inference_mode():
            scores_batch = torch.sigmoid(model(**encoded).logits).detach().cpu().tolist()

        for row, scores in zip(batch_rows, scores_batch):
            predicted = {
                label for label, score in zip(label_order, scores)
                if score >= args.threshold
            }
            if any(label != ModerationLabel.SAFE.value for label in predicted):
                predicted.discard(ModerationLabel.SAFE.value)
            expected = set(row["labels"])
            if predicted == expected:
                exact += 1
            primary = resolve_primary_label((ModerationLabel(label) for label in predicted)).value
            primary_ok += primary == row["primary_label"]
            for label in label_names:
                if label in predicted and label in expected:
                    counts[label]["tp"] += 1
                elif label in predicted:
                    counts[label]["fp"] += 1
                elif label in expected:
                    counts[label]["fn"] += 1

        done = offset + len(batch_rows)
        if done % max(args.batch_size, 1000) < args.batch_size or done == len(rows):
            elapsed = perf_counter() - started
            print(f"processed={done}/{len(rows)} elapsed_s={elapsed:.1f}", flush=True)

    aggregate, per_label = _metrics(counts, label_names)
    report = {
        "model_dir": str(args.model_dir),
        "dataset": str(args.dataset),
        "rows": len(rows),
        "device": device,
        "batch_size": args.batch_size,
        "threshold": args.threshold,
        "primary_accuracy": round(primary_ok / len(rows), 6),
        "label_exact_accuracy": round(exact / len(rows), 6),
        **aggregate,
        "per_label": per_label,
        "runtime_seconds": round(perf_counter() - started, 2),
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

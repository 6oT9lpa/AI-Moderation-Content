from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.rubert.rubert_training_config import RuBertTrainingConfig

# Use the same final audited export as the training entrypoint by default.
DATASET_DIR = PROJECT_ROOT / "export" / "moderation_dataset_v3_80_10_10"
DEFAULT_MODEL_DIR = Path("models/rubert-tiny2-moderation-trained")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


def _predict(model_dir: Path, rows: list[dict[str, Any]], *, batch_size: int) -> tuple[np.ndarray, np.ndarray, list[str]]:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    config = RuBertTrainingConfig.load()
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_dir,
        local_files_only=True,
        use_safetensors=True,
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()

    probabilities: list[np.ndarray] = []
    for start in range(0, len(rows), batch_size):
        batch_rows = rows[start : start + batch_size]
        batch = tokenizer(
            [row["text"] for row in batch_rows],
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=config.model.max_length,
        ).to(device)
        with torch.inference_mode():
            logits = model(**batch).logits.detach().cpu().numpy()
        probabilities.append(_sigmoid(logits))

    labels = np.asarray([row["labels"] for row in rows], dtype=np.int32)
    label_names = [model.config.id2label[index] for index in range(model.config.num_labels)]
    return np.vstack(probabilities), labels, label_names


def _metrics(probabilities: np.ndarray, labels: np.ndarray, thresholds: np.ndarray) -> dict[str, Any]:
    from sklearn.metrics import f1_score, precision_score, recall_score

    predictions = (probabilities >= thresholds).astype(np.int32)
    return {
        "micro_f1": float(f1_score(labels, predictions, average="micro", zero_division=0)),
        "macro_f1": float(f1_score(labels, predictions, average="macro", zero_division=0)),
        "micro_precision": float(precision_score(labels, predictions, average="micro", zero_division=0)),
        "micro_recall": float(recall_score(labels, predictions, average="micro", zero_division=0)),
        "exact_match": float(np.all(predictions == labels, axis=1).mean()),
        "positive_predictions": int(predictions.sum()),
        "positive_targets": int(labels.sum()),
    }


def _tune_thresholds(probabilities: np.ndarray, labels: np.ndarray, *, min_threshold: float) -> np.ndarray:
    from sklearn.metrics import f1_score

    thresholds = np.full(probabilities.shape[1], 0.5, dtype=np.float32)
    grid = np.asarray(
        [
            0.1,
            0.12,
            0.15,
            0.2,
            0.25,
            0.3,
            0.35,
            0.4,
            0.45,
            0.5,
            0.55,
            0.6,
            0.65,
            0.68,
            0.69,
            0.7,
            0.75,
            0.8,
        ]
    )
    grid = grid[grid >= min_threshold]
    for index in range(probabilities.shape[1]):
        target = labels[:, index]
        if target.sum() == 0:
            continue
        best_threshold = 0.5
        best_score = -1.0
        for threshold in grid:
            score = f1_score(target, (probabilities[:, index] >= threshold).astype(np.int32), zero_division=0)
            if score > best_score:
                best_score = score
                best_threshold = float(threshold)
        thresholds[index] = best_threshold
    return thresholds


def evaluate(
    *,
    model_dir: Path,
    dataset_dir: Path,
    split: str,
    batch_size: int,
    tune_thresholds: bool,
    save_thresholds: bool,
    min_threshold: float,
    thresholds_file: Path | None = None,
) -> dict[str, Any]:
    rows = _load_jsonl(dataset_dir / f"{split}.jsonl")
    probabilities, labels, label_names = _predict(model_dir, rows, batch_size=batch_size)
    if thresholds_file is not None:
        thresholds_data = json.loads(thresholds_file.read_text(encoding="utf-8"))
        thresholds = np.asarray([float(thresholds_data.get(label, 0.5)) for label in label_names], dtype=np.float32)
    elif tune_thresholds:
        thresholds = _tune_thresholds(probabilities, labels, min_threshold=min_threshold)
    else:
        thresholds = np.full(labels.shape[1], 0.5)
    result = {
        "split": split,
        "rows": len(rows),
        "thresholds": {label: round(float(threshold), 4) for label, threshold in zip(label_names, thresholds)},
        "metrics": _metrics(probabilities, labels, thresholds),
    }
    if save_thresholds:
        path = model_dir / "thresholds.json"
        path.write_text(json.dumps(result["thresholds"], ensure_ascii=False, indent=2), encoding="utf-8")
        result["thresholds_path"] = str(path)
    return result


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Evaluate and calibrate trained ruBERT moderation classifier.")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--split", choices=["train", "validation", "test"], default="validation")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--tune-thresholds", action="store_true")
    parser.add_argument("--save-thresholds", action="store_true")
    parser.add_argument("--min-threshold", type=float, default=0.15)
    parser.add_argument("--thresholds-file", type=Path, default=None)
    args = parser.parse_args()

    result = evaluate(
        model_dir=args.model_dir,
        dataset_dir=args.dataset_dir,
        split=args.split,
        batch_size=args.batch_size,
        tune_thresholds=args.tune_thresholds,
        save_thresholds=args.save_thresholds,
        min_threshold=args.min_threshold,
        thresholds_file=args.thresholds_file,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
